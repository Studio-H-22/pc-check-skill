"""Kreditmentes, egyszeri nyilvános Facebook Marketplace-gyűjtés.
Nincs fizetős API, proxy, bejelentkezési adat vagy végtelen újrapróbálás.
"""
import argparse,json,re,time
from pathlib import Path
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright

def extract_records(html):
    found={}
    def walk(obj):
        if isinstance(obj,dict):
            title=obj.get('marketplace_listing_title')
            ident=str(obj.get('id',''))
            if title and ident.isdigit():
                found[ident]={'id':ident,'title':title,'url':f'https://www.facebook.com/marketplace/item/{ident}/','price':obj.get('listing_price'), 'location':obj.get('location'),'description':obj.get('redacted_description') or obj.get('description')}
            for v in obj.values():walk(v)
        elif isinstance(obj,list):
            for v in obj:walk(v)
    for raw in re.findall(r'<script\b[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',html,re.S):
        try:walk(json.loads(raw))
        except (ValueError,RecursionError):pass
    return list(found.values())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--keyword',default='pc 32gb')
    ap.add_argument('--location',default='budapest')
    ap.add_argument('--min-price',type=int,default=100000)
    ap.add_argument('--max-price',type=int,default=400000)
    ap.add_argument('--limit',type=int,default=50)
    ap.add_argument('--details',type=int,default=5)
    ap.add_argument('--timeout',type=int,default=60)
    ap.add_argument('--browser-executable')
    ap.add_argument('--output',default='facebook-pc.json')
    a=ap.parse_args()
    if not re.fullmatch(r'[a-z0-9-]+',a.location):ap.error('Érvénytelen hely-útvonal')
    if a.limit<1 or a.details<0 or a.timeout<1:ap.error('Pozitív korlát szükséges')
    started=time.monotonic(); deadline=started+a.timeout
    url=f'https://www.facebook.com/marketplace/{a.location}/search/?'+urlencode({'query':a.keyword,'minPrice':a.min_price,'maxPrice':a.max_price})
    result={'source':'facebook-public-local','search_url':url,'status':'partial','records':[],'scraper_cost_usd':0,'limits':{'items':a.limit,'details':a.details,'seconds':a.timeout},'notes':[]}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,**({'executable_path':a.browser_executable} if a.browser_executable else {}))
        try:
            page=browser.new_page(locale='en-US')
            page.set_default_timeout(5000)
            page.goto(url,wait_until='domcontentloaded',timeout=min(a.timeout*1000,20000))
            for label in ['Decline optional cookies','Allow all cookies','Accept All']:
                button=page.get_by_role('button',name=label,exact=True)
                if button.count() and button.first.is_visible():button.first.click();break
            records={}; unchanged=0
            while time.monotonic()<deadline:
                html=page.content()
                for r in extract_records(html):records[r['id']]=r
                for el in page.locator('a[href*="/marketplace/item/"]').all()[:a.limit]:
                    href=el.get_attribute('href') or ''; m=re.search(r'/marketplace/item/(\d+)',href)
                    if m and m[1] not in records:
                        records[m[1]]={'id':m[1],'url':f'https://www.facebook.com/marketplace/item/{m[1]}/','card_text':el.inner_text(),'title':None,'price':None,'location':None,'description':None}
                if records or '/ineligible' in page.url or '/checkpoint' in page.url:break
                if page.get_by_role('textbox',name=re.compile('Email|phone',re.I)).count():
                    result['status']='login_required';break
                page.wait_for_timeout(1000);unchanged+=1
                if unchanged>=5:break
            result['records']=list(records.values())[:a.limit]
            if '/ineligible' in page.url:result['status']='marketplace_ineligible'
            elif '/checkpoint' in page.url:result['status']='checkpoint_required'
            elif not records and result['status']=='partial':result['status']='no_accessible_records'
            elif records:result['status']='partial'
            for r in result['records'][:a.details]:
                if time.monotonic()>=deadline:break
                try:
                    page.goto(r['url'],wait_until='domcontentloaded',timeout=min(15000,max(1,int((deadline-time.monotonic())*1000))))
                    for label in ['Decline optional cookies','Allow all cookies']:
                        btn=page.get_by_role('button',name=label,exact=True)
                        if btn.count() and btn.first.is_visible():btn.first.click();break
                    try:page.get_by_text('Details',exact=True).first.wait_for(state='visible',timeout=min(5000,max(1,int((deadline-time.monotonic())*1000))))
                    except Exception:pass
                    # Keep only visible description evidence; never assume card text is a description.
                    r['detail_text']=page.locator('body').inner_text()[:30000]
                    detail_rows=extract_records(page.content())
                    match=next((x for x in detail_rows if x['id']==r['id']),None)
                    if match and match.get('description'):r['description']=match['description']
                    elif '\nDetails\n' in r['detail_text']:
                        section=r['detail_text'].split('\nDetails\n',1)[1]
                        for end in ['\nSeller information\n','\nSeller details\n','\nSend seller a message\n']:
                            section=section.split(end,1)[0]
                        r['description_evidence']=section.strip()
                    r['detail_status']='public_details_read' if r.get('description') or r.get('description_evidence') else ('login_required' if page.get_by_role('textbox',name=re.compile('Email|phone',re.I)).count() else 'no_description')
                except Exception as e:r['detail_status']=type(e).__name__
            result['notes'].append('Nyilvános, bejelentkezés nélküli próba; ár/hely/RAM utószűrés szükséges. A keresés és időkorlát nem teljes kínálat.')
        except Exception as e:
            result['status']='technical_error';result['error']=type(e).__name__+': '+str(e)[:500]
        finally:browser.close()
    result['elapsed_seconds']=round(time.monotonic()-started,2)
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','elapsed_seconds','scraper_cost_usd']},ensure_ascii=False), 'records='+str(len(result['records'])))
if __name__=='__main__':main()

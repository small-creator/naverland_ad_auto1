import asyncio
import json
import os
import subprocess
import time
from typing import Optional, Dict, List, Callable
from playwright.async_api import async_playwright
import sys

if getattr(sys, 'frozen', False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")

CONCURRENCY = 5
BASE_URL = "https://new.land.naver.com/api/articles"

def _fetch_properties_via_curl(realtor_id: str, authorization: str, cookie_str: str, progress_callback: Callable) -> list:
    all_properties = []
    page = 1
    progress_callback(f"ID '{realtor_id}' 님의 광고중인 모든 매물을 가져옵니다...")

    while True:
        url = (
            f"{BASE_URL}?realtorId={realtor_id}&page={page}"
            f"&order=rank&tradeType=&realEstateType=&isFixed=false"
        )
        cmd = [
            "curl", url,
            "-s",
            "-H", "accept: */*",
            "-H", "accept-language: ko,en-US;q=0.9,en;q=0.8",
            "-H", f"authorization: Bearer {authorization}",
            "-b", cookie_str,
            "-H", "priority: u=1, i",
            "-H", "referer: https://new.land.naver.com/",
            "-H", 'sec-ch-ua: "Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
            "-H", "sec-ch-ua-mobile: ?0",
            "-H", 'sec-ch-ua-platform: "Windows"',
            "-H", "sec-fetch-dest: empty",
            "-H", "sec-fetch-mode: cors",
            "-H", "sec-fetch-site: same-origin",
            "-H", "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "-w", "\n%{http_code}",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=30, encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            lines = result.stdout.strip().rsplit("\n", 1)
            if len(lines) < 2:
                progress_callback(f"페이지 {page}: 응답 파싱 실패")
                break

            body, status_code = lines[0], lines[1].strip()
            if status_code != "200":
                progress_callback(f"페이지 {page}: HTTP {status_code} 오류")
                break

            data = json.loads(body)
            article_list = data.get("articleList", [])
            if not article_list:
                break

            for article in article_list:
                all_properties.append({
                    "atclNo": article.get("articleNo", ""),
                    "atclNm": article.get("articleName", ""),
                    "rletTpNm": article.get("tradeTypeName", ""),
                    "prc": article.get("dealOrWarrantPrc", ""),
                    "atclCfmYmd": article.get("articleConfirmYmd", ""),
                })

            progress_callback(f"페이지 {page}: {len(article_list)}개 매물 수집")

            if data.get("isMoreData") is False or len(article_list) < 20:
                break

            page += 1
            time.sleep(0.3)

        except subprocess.TimeoutExpired:
            progress_callback(f"페이지 {page}: curl 타임아웃")
            break
        except json.JSONDecodeError:
            progress_callback(f"페이지 {page}: JSON 파싱 오류")
            break
        except Exception as e:
            progress_callback(f"매물 수집 중 오류: {e}")
            break

    progress_callback(f"총 {len(all_properties)}개의 매물을 수집했습니다.")
    return all_properties

def _find_article_in_list(article_list: list, my_atcl_no: str) -> Optional[int]:
    for idx, sub_article in enumerate(article_list):
        detail = sub_article.get('articleDetail', {})
        num = detail.get('articleNumber') or sub_article.get('articleNo')
        if str(num) == str(my_atcl_no): return idx + 1
    return None

def _check_update_needed(article_list: list, my_atcl_no: str, my_article_confirm_ymd: str, my_rank: Optional[int]) -> bool:
    if len(article_list) <= 1: return False
    if my_rank == 1:
        has_same_date_competitor = False
        for competitor_article in article_list:
            comp_atcl_no = competitor_article.get('articleNo') or competitor_article.get('articleDetail', {}).get('articleNumber')
            if str(comp_atcl_no) == str(my_atcl_no): continue
            comp_confirm_ymd = competitor_article.get('articleConfirmYmd')
            if comp_confirm_ymd == my_article_confirm_ymd: has_same_date_competitor = True; break
        if not has_same_date_competitor: return False
    return True

def _check_floor_disclosure(my_floor_info: str, article_list: list) -> bool:
    if not my_floor_info or '/' not in my_floor_info: return False
    my_floor_type = my_floor_info.split('/')[0].strip()
    if my_floor_type not in ["저", "중", "고"]: return False
    for competitor_article in article_list:
        comp_floor_info = competitor_article.get('floorInfo')
        if comp_floor_info and '/' in comp_floor_info:
            comp_floor_part = comp_floor_info.split('/')[0].strip()
            if comp_floor_part.isdigit(): return True
    return False

async def check_rank_worker(page, prop: Dict, bearer_token: str) -> Dict:
    article_no = prop['atclNo']
    result = {
        "name": prop.get('atclNm', ''),
        "article_no": article_no,
        "rank": -1,
        "total": 0,
        "price": prop.get('prc', ''),
        "property_type": prop.get('rletTpNm', '매매'),
        "reg_date": prop.get('atclCfmYmd', '')
    }
    js_fetch = '''
        async ({ url, headers }) => {
            try {
                const response = await fetch(url, { headers });
                if (!response.ok) return { error: `HTTP ${response.status}` };
                return await response.json();
            } catch (e) { return { error: e.toString() }; }
        }
    '''
    try:
        api_url = f"https://new.land.naver.com/api/articles?index=0&representativeArticleNo={article_no}"
        headers = {
            'authorization': f'Bearer {bearer_token}',
            'referer': 'https://new.land.naver.com/complexes',
        }
        articles = await page.evaluate(js_fetch, {"url": api_url, "headers": headers})

        if isinstance(articles, dict) and articles.get('error'):
            result["error"] = articles['error']
        elif not isinstance(articles, list):
            result["error"] = "API 응답이 목록 형태가 아님"
        else:
            rank = _find_article_in_list(articles, article_no)
            my_article_data = next((a for a in articles if str(a.get('articleNo') or a.get('articleDetail', {}).get('articleNumber')) == str(article_no)), None)

            if my_article_data:
                dong = my_article_data.get('buildingName', '')
                floor_info = my_article_data.get('floorInfo', '')
                prop_type = my_article_data.get('tradeTypeName', prop.get('rletTpNm', ''))
                deposit_price = my_article_data.get('dealOrWarrantPrc', prop.get('prc', ''))

                if prop_type == '월세':
                    rent_price = my_article_data.get('rentPrc', '')
                    price = f"{deposit_price}/{rent_price}" if rent_price else deposit_price
                else:
                    price = deposit_price

                full_name = f"{prop.get('atclNm', '')} {dong}"
                if floor_info and '/' in floor_info:
                    full_name += f" {floor_info.split('/')[0]}층"

                result['name'] = full_name.strip()
                result['price'] = price
                result['property_type'] = prop_type

                update_needed = _check_update_needed(articles, article_no, my_article_data.get('articleConfirmYmd', ''), rank)
                floor_disclosed = _check_floor_disclosure(my_article_data.get('floorInfo', ''), articles)
            else:
                update_needed = False
                floor_disclosed = False

            result.update({"rank": rank if rank is not None else -1, "total": len(articles),
                           "update_needed": update_needed, "floor_disclosed": floor_disclosed})
    except Exception as e:
        result["error"] = str(e)
    return result

async def run_real_logic(member_id: str, progress_callback: Callable, test_mode: bool = False):
    bearer_token, token_found_event = None, asyncio.Event()
    browser = None

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True, args=["--disable-gpu"])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                locale='ko-KR',
                timezone_id='Asia/Seoul'
            )

            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = {
                    runtime: {}
                };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ko-KR', 'ko', 'en-US', 'en']
                });
            """)

            auth_page = await context.new_page()

            async def handle_request(request):
                nonlocal bearer_token
                auth = request.headers.get('authorization')
                if auth and auth.lower().startswith('bearer ') and not bearer_token:
                    bearer_token = auth.split(' ')[-1]
                    token_found_event.set()
            auth_page.on('request', handle_request)

            try:
                progress_callback("\n인증 토큰 추출을 위해 브라우저를 실행합니다...")
                await auth_page.goto("https://new.land.naver.com/complexes/100")
                await asyncio.wait_for(token_found_event.wait(), timeout=30)
                progress_callback("성공적으로 Bearer 토큰을 찾았습니다.")
            except asyncio.TimeoutError:
                progress_callback("타임아웃: 새 토큰을 찾지 못했습니다.")

            if not bearer_token:
                progress_callback("오류: Bearer 토큰을 추출하지 못했습니다. 프로그램을 종료합니다.")
                return []

            cookies = await context.cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            await auth_page.close()

            properties_to_check = await asyncio.get_event_loop().run_in_executor(
                None, _fetch_properties_via_curl, member_id, bearer_token, cookie_str, progress_callback
            )

            if not properties_to_check:
                progress_callback("조회할 매물이 없습니다.")
                return []

            if test_mode:
                progress_callback(f"--- 테스트 모드: 상위 3개 매물만 조회합니다 ---")
                properties_to_check = properties_to_check[:3]

            progress_callback(f"ITEM_COUNT:{len(properties_to_check)}")

            progress_callback(f"\n--- 전체 매물 순위 병렬 조회 시작 (동시 {CONCURRENCY}개) ---")
            all_results = []
            property_chunks = [properties_to_check[i:i + CONCURRENCY] for i in range(0, len(properties_to_check), CONCURRENCY)]

            worker_pages = []
            for _ in range(CONCURRENCY):
                worker_pages.append(await context.new_page())
                await asyncio.sleep(0.5)
            for wp in worker_pages:
                await wp.context.add_cookies(cookies)
                await wp.goto("https://new.land.naver.com/complexes", wait_until="domcontentloaded")

            for i, chunk in enumerate(property_chunks):
                progress_callback(f"- 그룹 {i+1}/{len(property_chunks)} ({len(chunk)}개) 처리 중...")
                tasks = [check_rank_worker(worker_pages[j], prop, bearer_token) for j, prop in enumerate(chunk)]
                chunk_results = await asyncio.gather(*tasks)
                all_results.extend(chunk_results)
                if i + 1 < len(property_chunks): await asyncio.sleep(0.5)

            for worker_page in worker_pages:
                await worker_page.close()

            progress_callback("모든 순위 조회가 완료되었습니다.")
            return all_results

        finally:
            progress_callback("브라우저를 닫는 중입니다...")
            if browser:
                await browser.close()
            progress_callback("브라우저가 완전히 종료되었습니다.")

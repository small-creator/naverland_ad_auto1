import asyncio
import os
import json
from datetime import datetime
from playwright.async_api import async_playwright
import sys

if getattr(sys, 'frozen', False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")

class RealEstateAutomation:
    def __init__(self, headless=True):
        self.headless = headless

        self.login_id, self.login_pw = self.load_login_config()

        if not self.login_id or not self.login_pw:
                    
            self.login_id = "your_login_id"                 
            self.login_pw = "your_password"                

        self.login_url = "https://www.aipartner.com/integrated/login?serviceCode=1000"
        self.ad_list_url = "https://www.aipartner.com/offerings/ad_list"

        self.number_mapping = {}                      

        self.fullname_mapping = {}                       

        print(f"🔧 로그인 ID: {self.login_id}")
        print(f"🔒 비밀번호: {'*' * len(self.login_pw)}")

    def load_login_config(self):
        env_id = os.getenv("LOGIN_ID")
        env_pw = os.getenv("LOGIN_PASSWORD")
        if env_id and env_pw:
            return env_id, env_pw
        
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    login_id = config.get('ai_partner_login_id', '')
                    login_pw = config.get('ai_partner_password', '')
                    return login_id, login_pw
            return None, None
        except Exception as e:
            print(f"config.json 로드 중 오류: {e}")
            return None, None

    async def login(self, page, popup_messages=None):
        
        print("🔗 로그인 페이지로 이동 중...")

        await page.goto(self.login_url, timeout=60000, wait_until='domcontentloaded')
        await page.wait_for_selector('#member-id', timeout=30000)

        await page.fill('#member-id', self.login_id)
        await page.fill('#member-pw', self.login_pw)
        print("🔐 로그인 버튼 클릭...")
        await page.click('#integrated-login > a')

        try:
            await page.wait_for_url('**/offerings/ad_list', timeout=10000)
        except:
            await page.wait_for_timeout(2000)               

        if popup_messages:
            for msg in popup_messages:
                if "등록되지 않은 아이디" in msg or "잘못된 비밀번호" in msg or "아이디" in msg and "비밀번호" in msg:
                    raise Exception(f"❌ 로그인 실패: {msg}\n\nconfig.json 파일의 아이디/비밀번호를 확인해주세요.")

        print("✅ 로그인 완료")

    async def find_ended_property_and_re_register(self, page, property_number):
        
        print(f"[재시도] 종료매물에서 매물번호 {property_number} 검색 중...")

        try:
            print("🌐 매물 리스트 페이지로 이동 중...")
            await page.goto(self.ad_list_url, timeout=60000, wait_until='domcontentloaded')

            print("⏳ 매물 테이블 로딩 대기 중...")
            await page.wait_for_selector('table tbody tr', state='visible', timeout=30000)
            print("✅ 매물 테이블 로딩 완료")

            try:
                            
                await page.evaluate()
                print("✅ 팝업 오버레이 제거 완료")

                ad_end_button = await page.wait_for_selector('#wrap > div.container > div > div > div.sectionWrap > div.statusWrap.ver3 > div.statusItem.statusAdEnd.GTM_offerings_ad_list_end_ad', timeout=10000)
                await ad_end_button.click()
                print("광고종료 버튼 클릭 완료")

                print("⏳ 종료매물 목록 로딩 대기 중...")
                await page.wait_for_selector('table tbody tr', state='visible', timeout=10000)
                print("✅ 종료매물 목록 로딩 완료")

                await page.evaluate()
                print("✅ 종료매물 목록 로딩 후 팝업 오버레이 제거 완료")

                print("📍 종료매물 재시도: 1페이지만 확인")
            except Exception as e:
                print(f"광고종료 버튼 클릭 실패: {e}")
                if not self.headless:
                    print("\n⚠️  디버깅 모드: 브라우저 확인 후 Enter를 눌러주세요...")
                    input()
                return False

            try:
                end_rows = await page.query_selector_all('#wrap > div.container > div > div > div.sectionWrap > div.singleSection.listSection > div.listWrap > table > tbody > tr')
                print(f"종료매물 목록에서 {len(end_rows)}개 행 확인")

                for row in end_rows:
                    number_cell = await row.query_selector('td:nth-child(3) > div.numberN')
                    if number_cell:
                        number_text = await number_cell.inner_text()
                        if property_number in number_text.strip():
                            print(f"종료매물에서 매물번호 {property_number} 발견!")
                                                                         
                            number_cell_A = await row.query_selector('td:nth-child(3) > div.numberA')
                            if number_cell_A:
                                number_A = await number_cell_A.inner_text()
                                number_A = number_A.strip()
                                if number_A:
                                    self.number_mapping[property_number] = number_A
                                    print(f"   📋 numberA 추출: {property_number} → {number_A}")

                            await page.evaluate()
                            print("   ✅ 재광고 버튼 클릭 전 팝업 제거 완료 (재시도)")

                            re_ad_button = await row.query_selector('a#reReg')
                            if re_ad_button:
                                await re_ad_button.click()
                                print("재광고 버튼 클릭 완료")

                                print("⏳ 광고등록 페이지 이동 대기 중...")
                                await page.wait_for_url('**/offerings/ad_regist', timeout=15000)
                                print("✅ 광고등록 페이지 이동 완료")
                                return True
                            else:
                                print("재광고 버튼을 찾을 수 없습니다.")
                                if not self.headless:
                                    print("\n⚠️  디버깅 모드: 브라우저 확인 후 Enter를 눌러주세요...")
                                    input()

                print(f"종료매물에서 매물번호 {property_number}를 찾을 수 없습니다.")
                if not self.headless:
                    print("\n⚠️  디버깅 모드: 브라우저 확인 후 Enter를 눌러주세요...")
                    input()
                return False

            except Exception as e:
                print(f"재광고 버튼 클릭 중 오류: {e}")
                if not self.headless:
                    print("\n⚠️  디버깅 모드: 브라우저 확인 후 Enter를 눌러주세요...")
                    input()
                return False

        except Exception as e:
            print(f"[재시도] 종료매물 검색 중 전체 오류: {e}")
            if not self.headless:
                print("\n⚠️  디버깅 모드: 브라우저 확인 후 Enter를 눌러주세요...")
                input()
            return False

    async def find_property_and_end_exposure(self, page, property_number):
        
        print(f"매물번호 {property_number} 검색 중...")

        try:
            print("🌐 매물 리스트 페이지로 이동 중...")
            await page.goto(self.ad_list_url, timeout=60000, wait_until='domcontentloaded')

            print("⏳ 매물 테이블 로딩 대기 중...")
            await page.wait_for_selector('table tbody tr', state='visible', timeout=30000)
            print("✅ 매물 테이블 로딩 완료")

            await page.evaluate()
            print("✅ 매물 리스트 로딩 후 팝업 오버레이 제거 완료")

            property_found = False
            current_page = 1

            while not property_found:
                print(f"=== {current_page}페이지에서 매물 검색 중 ===")

                rows = await page.query_selector_all('#wrap > div.container > div > div > div.sectionWrap > div.singleSection.listSection > div.listWrap > table > tbody > tr')
                print(f"{current_page}페이지: 총 {len(rows)}개의 매물을 확인합니다.")

                for i, row in enumerate(rows, 1):
                    number_cell = await row.query_selector('td:nth-child(3) > div.numberN')
                    if number_cell:
                        number_text = await number_cell.inner_text()
                        if property_number in number_text.strip():
                            print(f"매물번호 {property_number} 발견! ({current_page}페이지, 행: {i})")

                            ad_type_cell = await row.query_selector('td:nth-child(8)')
                            if ad_type_cell:
                                ad_type_text = await ad_type_cell.inner_text()
                                print(f"광고유형 확인: {ad_type_text.strip()}")

                                if "로켓등록" not in ad_type_text:
                                    print(f"❌ 로켓등록 상품이 아닙니다. (광고유형: {ad_type_text.strip()})")
                                    return {'step': '광고유형 확인', 'reason': '로켓등록 상품이 아닙니다', 'no_retry': True}

                                print(f"✅ 로켓등록 상품 확인됨")
                            else:
                                print(f"⚠️ 광고유형 컬럼을 찾을 수 없습니다.")

                            end_button = await row.query_selector('#naverEnd')
                            if end_button:
                                print("노출종료 버튼 클릭 시도 중...")

                                try:
                                                                 
                                    print("🖱️  노출종료 버튼을 클릭합니다...")
                                    await end_button.click()
                                    print("✅ 노출종료 버튼 클릭 완료")

                                    print("⏳ 팝업 처리 대기 중...")
                                    await page.wait_for_timeout(1000)

                                    print("⏳ 광고종료 버튼 활성화 대기 중...")
                                    await page.wait_for_selector('.statusAdEnd', state='visible', timeout=10000)
                                    print("✅ 노출종료 완료 (광고종료 버튼 활성화됨)")

                                    property_found = True
                                    break

                                except Exception as e:
                                    print(f"노출종료 버튼 클릭 중 오류: {e}")
                            else:
                                print("노출종료 버튼을 찾을 수 없습니다.")

                if property_found:
                    break

                try:
                    next_button = await page.query_selector('.pagination a.btnArrow.next')
                    if next_button:
                        next_data_value = await next_button.get_attribute('data-value')
                        if next_data_value and int(next_data_value) <= current_page:
                            print("마지막 페이지에 도달했습니다.")
                            break

                        print(f"📄 {current_page+1}페이지로 이동 중...")
                        await next_button.click()

                        await page.wait_for_timeout(2000)

                        print("⏳ 다음 페이지 로딩 대기 중...")
                        try:
                            await page.wait_for_selector('table tbody tr', timeout=15000)
                            await page.wait_for_timeout(1000)
                            print(f"✅ {current_page+1}페이지 로딩 완료")
                        except:
                            print(f"⚠️  {current_page+1}페이지 로딩 실패 - 계속 진행")

                        await page.evaluate()
                        print(f"✅ {current_page+1}페이지 로딩 후 팝업 제거 완료")

                        current_page += 1

                    else:
                        print("다음 페이지 버튼을 찾을 수 없습니다.")
                        break
                except Exception as e:
                    print(f"페이지 이동 중 오류: {e}")
                    break

            if not property_found:
                print(f"매물번호 {property_number}를 찾을 수 없습니다.")
                return False

            try:
                                                              
                await page.evaluate()
                print("✅ 팝업 오버레이 제거 완료")

                ad_end_button = await page.wait_for_selector('#wrap > div.container > div > div > div.sectionWrap > div.statusWrap.ver3 > div.statusItem.statusAdEnd.GTM_offerings_ad_list_end_ad', timeout=10000)
                await ad_end_button.click()
                print("광고종료 버튼 클릭 완료")

                print("⏳ 종료매물 목록 로딩 대기 중...")
                await page.wait_for_selector('table tbody tr', state='visible', timeout=10000)
                print("✅ 종료매물 목록 로딩 완료")

                await page.evaluate()
                print("✅ 종료매물 목록 로딩 후 팝업 오버레이 제거 완료")
            except Exception as e:
                print(f"광고종료 버튼 클릭 실패: {e}")
                if not self.headless:
                    print("\n⚠️  디버깅 모드: 브라우저 확인 후 Enter를 눌러주세요...")
                    input()
                return False

            try:

                end_rows = await page.query_selector_all('#wrap > div.container > div > div > div.sectionWrap > div.singleSection.listSection > div.listWrap > table > tbody > tr')
                print(f"종료매물 목록에서 {len(end_rows)}개 행 확인")

                for row in end_rows:
                    number_cell = await row.query_selector('td:nth-child(3) > div.numberN')
                    if number_cell:
                        number_text = await number_cell.inner_text()
                        if property_number in number_text.strip():
                            print(f"종료매물에서 매물번호 {property_number} 발견!")

                            number_cell_A = await row.query_selector('td:nth-child(3) > div.numberA')
                            if number_cell_A:
                                number_A = await number_cell_A.inner_text()
                                number_A = number_A.strip()
                                if number_A:
                                    self.number_mapping[property_number] = number_A
                                    print(f"   📋 numberA 추출: {property_number} → {number_A}")

                            await page.evaluate()
                            print("   ✅ 재광고 버튼 클릭 전 팝업 제거 완료 (일반)")

                            re_ad_button = await row.query_selector('a#reReg')
                            if re_ad_button:
                                await re_ad_button.click()
                                print("재광고 버튼 클릭 완료")

                                print("⏳ 광고등록 페이지 이동 대기 중...")
                                await page.wait_for_url('**/offerings/ad_regist', timeout=15000)
                                print("✅ 광고등록 페이지 이동 완료")
                                return True
                            else:
                                print("재광고 버튼을 찾을 수 없습니다.")
                                if not self.headless:
                                    print("\n⚠️  디버깅 모드: 브라우저 확인 후 Enter를 눌러주세요...")
                                    input()           

                print(f"종료매물에서 매물번호 {property_number}를 찾을 수 없습니다.")
                if not self.headless:
                    print("\n⚠️  디버깅 모드: 브라우저 확인 후 Enter를 눌러주세요...")
                    input()           
                return False

            except Exception as e:
                print(f"재광고 버튼 클릭 중 오류: {e}")
                if not self.headless:
                    print("\n⚠️  디버깅 모드: 브라우저 확인 후 Enter를 눌러주세요...")
                    input()
                return False

        except Exception as e:
            print(f"매물 검색 중 전체 오류: {e}")
            if not self.headless:
                print("\n⚠️  디버깅 모드: 브라우저 확인 후 Enter를 눌러주세요...")
                input()
            return False

    async def remove_popups(self, page):
        try:
            await page.evaluate()
        except:
            pass

    async def process_ad_regist(self, page):
        print("광고등록 페이지 처리 중...")
        await page.wait_for_url('**/offerings/ad_regist', timeout=20000)
        await self.remove_popups(page)
        await page.wait_for_timeout(500)

        print("⏳ 광고하기 버튼 로딩 대기 중...")
        try:
            await page.wait_for_selector('text=광고하기', state='visible', timeout=10000)
            print("✅ 광고하기 버튼 로딩 완료")
        except:
            print("⚠️ 광고하기 버튼 텍스트 선택자 실패, 대체 선택자 시도")

        try:
            await page.click('text=광고하기')
            print("광고하기 버튼 클릭 완료")
        except:
            ad_button = await page.query_selector('button:has-text("광고하기"), input[value*="광고"], a:has-text("광고하기")')
            if ad_button:
                await ad_button.click()
                print("광고하기 버튼 클릭 완료")
            else:
                print("광고하기 버튼을 찾을 수 없습니다.")
                return False

        print("⏳ 결제 페이지 로딩 대기 중...")
        await page.wait_for_selector('#consentMobile2', state='attached', timeout=10000)
        print("✅ 결제 페이지 로딩 완료")
        return True

    async def process_payment(self, page, popup_messages):
        
        print("결제 페이지에서 처리 중...")

        checkbox_checked = False
        for attempt in range(3):
            try:
                await page.wait_for_selector('#consentMobile2', state='attached', timeout=10000)

                result = await page.evaluate()

                await page.wait_for_timeout(500)

                if result:
                    print(f"✅ 체크박스 클릭 완료 (시도 {attempt + 1})")
                    checkbox_checked = True
                    break
                else:
                    print(f"⚠️ 체크박스 클릭했지만 체크 안됨 (시도 {attempt + 1})")
                    if attempt < 2:
                        await page.wait_for_timeout(500)
                        continue
            except Exception as e:
                print(f"⚠️ 체크박스 클릭 시도 {attempt + 1} 실패: {e}")
                if attempt < 2:
                    await page.wait_for_timeout(500)
                    continue

        if not checkbox_checked:
            print("❌ 체크박스 클릭 실패")
            return (False, "failed")

        payment_button = await page.query_selector('#naverSendSave')
        if not payment_button:
            print("❌ 결제하기 버튼을 찾을 수 없습니다.")
            return (False, "failed")

        saved_message_found = False
        for msg in popup_messages:
            if "매물을 저장 하였습니다" in msg:
                saved_message_found = True
                break

        popup_messages.clear()

        await payment_button.click()
        print("✅ 결제하기 버튼 클릭 완료")

        print("⏳ 결제 완료 대기 중...")
        payment_success = False
        wait_time = 0
        max_wait = 20

        while wait_time < max_wait:
            await page.wait_for_timeout(1000)
            wait_time += 1

            for msg in popup_messages:
                        
                if "로켓전송이 완료되었습니다" in msg:
                    print(f"✅ 결제 성공 확인: {msg}")
                    payment_success = True
                    break

                elif "결제수단을 선택해 주세요" in msg or "결제수단을 선택" in msg:
                    print(f"💰 충전금 부족 감지: {msg}")
                    print(f"⚠️ 충전금이 부족합니다. 충전 후 다시 시도해주세요.")
                    return (False, "insufficient_balance")

                elif "매물을 저장 하였습니다" in msg:
                    print(f"ℹ️ 매물 저장 확인: {msg} (계속 처리 중...)")
                    saved_message_found = True
                                                        
            if payment_success:
                break

            for msg in popup_messages:
                if "동의해 주세요" in msg or "동의" in msg:
                    print(f"❌ 체크박스 미동의로 결제 실패: {msg}")
                    return (False, "failed")

        if payment_success:
            return (True, "success")
        else:
                                          
            print(f"❌ 결제 완료 확인 실패 - '로켓전송이 완료되었습니다' alert를 받지 못함")
            print(f"📋 받은 팝업 메시지: {popup_messages if popup_messages else '없음'}")

            if saved_message_found:
                print(f"🔄 매물이 저장되었으나 결제는 미완료 - 재시도 필요")
                return (False, "saved")
            else:
                return (False, "failed")

    async def return_to_list(self, page):
        
        print("목록 버튼 클릭하여 매물리스트로 돌아가는 중...")

        try:
                                                
            await page.evaluate()
            print("✅ 로딩 오버레이 제거 완료")

            list_button = await page.wait_for_selector('#btnCancel', timeout=10000)
            if list_button:
                await list_button.click()
                print("목록 버튼 클릭 완료")
                await page.wait_for_timeout(1000)
                return True
            else:
                print("목록 버튼을 찾을 수 없습니다.")
                return False
        except Exception as e:
            print(f"목록 버튼 클릭 실패: {e}")
            return False

    async def handle_popup_overlay(self, page):
        
        try:
                                            
            try:
                await page.keyboard.press('Escape')
                await page.wait_for_timeout(300)
                print("✅ ESC 키로 팝업 닫기 시도")
            except:
                pass

            close_selectors = [
                'button[class*="close"]',
                'button[class*="dismiss"]',
                'span[class*="close"]',
                'div[class*="close"]',
                'a[class*="close"]',
                '.close',
                '.dismiss',
                '.x-button'
            ]

            for close_selector in close_selectors:
                try:
                    close_button = await page.query_selector(close_selector)
                    if close_button:
                        await close_button.click()
                        print(f"✅ {close_selector} 닫기 버튼 클릭 성공")
                        await page.wait_for_timeout(300)
                        return
                except:
                    continue

            popup_selectors = [
                'img[src*="popup"]',
                'div[class*="popup"]',
                'div[id*="popup"]',
                '.modal',
                '.overlay'
            ]

            for selector in popup_selectors:
                try:
                    popup_elements = await page.query_selector_all(selector)
                    if popup_elements:
                        print(f"🚨 {selector} 팝업 감지 ({len(popup_elements)}개)")
                        for popup in popup_elements:
                            try:
                                                                          
                                await popup.evaluate('el => el.style.display = "none"')
                            except:
                                pass
                        print(f"✅ {selector} 팝업 제거 완료")
                except:
                    continue

            await page.wait_for_timeout(300)

        except Exception as e:
            print(f"⚠️ 팝업 오버레이 처리 중 오류 (계속 진행): {e}")

    async def process_single_property(self, page, property_number, popup_messages, progress_callback=None):
        
        print(f"\n{'='*50}")
        print(f"매물번호 {property_number} 처리 시작")
        print(f"{'='*50}")

        if progress_callback:
            progress_callback(f"매물번호 {property_number} 처리 시작")

        try:
                             
            if progress_callback:
                progress_callback(f"매물번호 {property_number} 검색 및 노출종료 중...")

            exposure_result = await self.find_property_and_end_exposure(page, property_number)
                                                         
            if isinstance(exposure_result, dict):
                return exposure_result
            if not exposure_result:
                return {'step': '노출종료', 'reason': '매물을 찾을 수 없거나 노출종료 실패'}

            if progress_callback:
                progress_callback(f"매물번호 {property_number} 광고등록 처리 중...")

            if not await self.process_ad_regist(page):
                return {'step': '광고등록', 'reason': '광고등록 페이지 처리 실패'}

            if progress_callback:
                progress_callback(f"매물번호 {property_number} 결제 처리 중...")

            payment_success, payment_status = await self.process_payment(page, popup_messages)

            if payment_success:
                       
                print(f"  🎉 매물번호 {property_number} 실제 업데이트 완료!")
                if progress_callback:
                    progress_callback(f"매물번호 {property_number} 처리 완료!")
                print(f"  ✅ 매물번호 {property_number} 처리 완료")

                try:
                    await page.goto(self.ad_list_url, timeout=10000, wait_until='domcontentloaded')
                    await page.wait_for_timeout(1000)
                    print("✅ 매물 리스트 페이지로 복귀 완료")
                except Exception as e:
                    print(f"⚠️ 목록 복귀 중 예외: {e} - 하지만 매물은 이미 성공적으로 처리되었습니다.")

                return True
            else:
                                            
                return {'step': '결제', 'reason': f'결제 처리 실패 - {payment_status}', 'payment_status': payment_status}

        except Exception as e:
            error_msg = f"매물번호 {property_number} 처리 중 오류 발생: {e}"
            if progress_callback:
                progress_callback(error_msg)
            print(error_msg)
            return {'step': '예외 발생', 'reason': str(e)}

    async def batch_end_exposure(self, page, property_numbers, popup_messages, progress_callback=None):
        
        print(f"\n{'='*60}")
        print(f"[1단계] 모든 매물 노출종료 시작 ({len(property_numbers)}개)")
        print(f"{'='*60}")

        successful_exposures = []
        failed_exposures = {}

        for i, property_number in enumerate(property_numbers, 1):
            print(f"\n[노출종료 {i}/{len(property_numbers)}] 매물번호 {property_number}")
            if progress_callback:
                progress_callback(f"[1단계 {i}/{len(property_numbers)}] 매물 {property_number} 노출종료 중...")

            try:
                                                                   
                print(f"🌐 매물 리스트 페이지로 이동 중...")
                if progress_callback:
                    progress_callback(f"[1단계 {i}/{len(property_numbers)}] 매물 리스트 페이지로 이동 중...")
                await page.goto(self.ad_list_url, timeout=60000, wait_until='domcontentloaded')

                print(f"📋 매물 테이블 로딩 대기 중...")
                if progress_callback:
                    progress_callback(f"[1단계 {i}/{len(property_numbers)}] 매물 테이블 로딩 대기 중...")
                try:
                    await page.wait_for_selector('table tbody tr.adComplete', state='visible', timeout=30000)
                    await page.wait_for_selector('table tbody tr', state='visible', timeout=30000)
                    print(f"✅ 매물 테이블 로딩 완료")
                    if progress_callback:
                        progress_callback(f"[1단계 {i}/{len(property_numbers)}] 매물 테이블 로딩 완료")
                except Exception as e:
                    print(f"⚠️ 테이블 로딩 지연 - 재시도 중...")
                    await page.wait_for_timeout(2000)
                    try:
                        await page.wait_for_selector('table tbody tr', state='visible', timeout=30000)
                        await page.wait_for_timeout(1000)
                        print(f"✅ 매물 테이블 로딩 완료 (재시도 성공)")
                    except Exception as retry_error:
                        print(f"❌ 매물 테이블 로딩 실패: {retry_error}")
                        print(f"   현재 URL: {page.url}")
                                   
                        if self.headless:
                            try:
                                await page.screenshot(path=f"batch_table_error_{property_number}.png")
                                print(f"   📸 오류 스크린샷: batch_table_error_{property_number}.png")
                            except:
                                pass
                        raise

                await page.evaluate()
                print(f"   ✅ 팝업 제거 완료")

                property_found = False
                current_page = 1

                print(f"   ⏳ 1페이지 데이터 안정화 대기 중...")
                await page.wait_for_timeout(2000)

                while not property_found:
                    print(f"   📄 {current_page}페이지에서 검색 중...")
                    if progress_callback:
                        progress_callback(f"[1단계 {i}/{len(property_numbers)}] {current_page}페이지에서 매물 {property_number} 검색 중...")

                    rows = await page.query_selector_all('#wrap > div.container > div > div > div.sectionWrap > div.singleSection.listSection > div.listWrap > table > tbody > tr')
                    print(f"   📊 현재 페이지 매물 수: {len(rows)}개")
                    if progress_callback:
                        progress_callback(f"[1단계 {i}/{len(property_numbers)}] {current_page}페이지 매물 수: {len(rows)}개")

                    for row in rows:
                        number_cell = await row.query_selector('td:nth-child(3) > div.numberN')
                        if number_cell:
                            number_text = await number_cell.inner_text()
                            if property_number in number_text.strip():
                                print(f"   🎯 매물번호 {property_number} 발견! ({current_page}페이지)")
                                if progress_callback:
                                    progress_callback(f"[1단계 {i}/{len(property_numbers)}] 매물 {property_number} 발견! ({current_page}페이지)")
                                property_found = True

                                ad_type_cell = await row.query_selector('td:nth-child(8)')
                                if ad_type_cell:
                                    ad_type_text = await ad_type_cell.inner_text()
                                    if "로켓등록" not in ad_type_text:
                                        print(f"   ❌ 로켓등록 상품이 아님 - 스킵")
                                        if progress_callback:
                                            progress_callback(f"[1단계 {i}/{len(property_numbers)}] 매물 {property_number} 로켓등록 아님 - 스킵")
                                        failed_exposures[property_number] = {'step': '광고유형 확인', 'reason': '로켓등록 아님', 'no_retry': True}
                                        break

                                if progress_callback:
                                    progress_callback(f"[1단계 {i}/{len(property_numbers)}] 매물 {property_number} 노출종료 버튼 클릭 중...")
                                end_button = await row.query_selector('#naverEnd')
                                if end_button:
                                    popup_messages.clear()

                                    await end_button.click()
                                    await page.wait_for_timeout(500)

                                    max_wait = 10
                                    wait_time = 0
                                    exposure_success = False
                                    exposure_failed = False

                                    while wait_time < max_wait:
                                        for msg in popup_messages:
                                            if "노출종료 했어요" in msg:
                                                print(f"   ✅ 노출종료 성공 확인: {msg}")
                                                exposure_success = True
                                                break
                                            elif "노출종료에 실패" in msg or "통신 중 오류" in msg:
                                                print(f"   ❌ 노출종료 실패: {msg}")
                                                if progress_callback:
                                                    progress_callback(f"[1단계 {i}/{len(property_numbers)}] 매물 {property_number} 노출종료 실패: {msg}")
                                                failed_exposures[property_number] = {'step': '노출종료', 'reason': msg}
                                                exposure_failed = True
                                                break

                                        if exposure_success or exposure_failed:
                                            break

                                        await page.wait_for_timeout(500)
                                        wait_time += 0.5

                                    if exposure_failed:
                                        break

                                    if exposure_success:
                                        if progress_callback:
                                            progress_callback(f"[1단계 {i}/{len(property_numbers)}] ✅ 매물 {property_number} 노출종료 성공!")
                                        successful_exposures.append(property_number)
                                    else:
                                        print(f"   ⚠️ 노출종료 결과 확인 타임아웃")
                                        if progress_callback:
                                            progress_callback(f"[1단계 {i}/{len(property_numbers)}] 매물 {property_number} 노출종료 결과 확인 타임아웃")
                                        failed_exposures[property_number] = {'step': '노출종료', 'reason': '결과 확인 타임아웃'}
                                else:
                                    print(f"   ❌ 노출종료 버튼 없음")
                                    if progress_callback:
                                        progress_callback(f"[1단계 {i}/{len(property_numbers)}] 매물 {property_number} 노출종료 버튼 없음")
                                    failed_exposures[property_number] = {'step': '노출종료', 'reason': '노출종료 버튼 없음'}
                                break

                    if property_found:
                        break

                    print(f"   ⏭️  다음 페이지로 이동 중... ({current_page} → {current_page + 1})")
                    if not await self.goto_next_page(page, current_page):
                        print(f"   ⚠️ 다음 페이지 이동 실패 - 검색 종료 (마지막 페이지)")
                        break
                    current_page += 1

                if not property_found:
                    print(f"   ❌ 매물을 찾을 수 없음 (총 {current_page}페이지 검색)")
                    if progress_callback:
                        progress_callback(f"[1단계 {i}/{len(property_numbers)}] ❌ 매물 {property_number} 찾을 수 없음 (총 {current_page}페이지 검색)")
                    failed_exposures[property_number] = {'step': '노출종료', 'reason': '매물을 찾을 수 없음'}

            except Exception as e:
                current_url = page.url
                error_msg = f"   ❌ 노출종료 실패: {e}"
                print(error_msg)
                print(f"   현재 URL: {current_url}")

                if progress_callback:
                    progress_callback(f"[1단계 {i}/{len(property_numbers)}] 매물 {property_number} 노출종료 실패: {str(e)[:100]}")

                if self.headless:
                    try:
                        screenshot_path = f"batch_error_{property_number}.png"
                        await page.screenshot(path=screenshot_path)
                        print(f"   📸 에러 스크린샷: {screenshot_path}")
                    except:
                        pass

                failed_exposures[property_number] = {'step': '노출종료', 'reason': str(e)}

            if i < len(property_numbers):
                await page.wait_for_timeout(1000)

        print(f"\n{'='*60}")
        print(f"[1단계 완료] 노출종료 성공: {len(successful_exposures)}개, 실패: {len(failed_exposures)}개")
        print(f"{'='*60}")

        return successful_exposures, failed_exposures

    async def goto_next_page(self, page, current_page):
        
        try:
            next_button = await page.query_selector('.pagination a.btnArrow.next')
            if next_button:
                next_data_value = await next_button.get_attribute('data-value')
                if next_data_value and int(next_data_value) <= current_page:
                    print(f"   ⚠️ 다음 페이지 버튼이 비활성화됨 (마지막 페이지)")
                    return False

                await next_button.click()
                await page.wait_for_timeout(2000)

                try:
                    await page.wait_for_selector('table tbody tr', timeout=10000)
                    await page.wait_for_timeout(1500)

                    await page.evaluate()
                    print(f"   ✅ {current_page + 1}페이지 로딩 완료")
                    return True
                except Exception as e:
                    print(f"   ❌ {current_page + 1}페이지 로딩 실패: {e}")
                    return False
            else:
                print(f"   ⚠️ 다음 페이지 버튼을 찾을 수 없음")
                return False
        except Exception as e:
            print(f"   ⚠️ 페이지 이동 중 오류: {e}")
            return False

    async def goto_next_page_ended(self, page, current_page):
        
        try:
            next_button = await page.query_selector('.pagination a.btnArrow.next')
            if next_button:
                next_data_value = await next_button.get_attribute('data-value')
                if next_data_value and int(next_data_value) <= current_page:
                    print(f"   ⚠️ 다음 페이지 버튼이 비활성화됨 (마지막 페이지)")
                    return False

                await next_button.click()
                await page.wait_for_timeout(2000)

                try:
                    await page.wait_for_selector('table tbody tr', timeout=15000)

                    await page.evaluate()
                    print(f"   ✅ 종료매물 {current_page + 1}페이지 로딩 완료")
                    return True
                except Exception as e:
                    print(f"   ❌ 종료매물 {current_page + 1}페이지 로딩 실패: {e}")
                    return False
            else:
                print(f"   ⚠️ 다음 페이지 버튼을 찾을 수 없음")
                return False
        except Exception as e:
            print(f"   ⚠️ 페이지 이동 중 오류: {e}")
            return False

    async def batch_process_ended_properties(self, page, property_numbers, popup_messages, progress_callback=None):
        
        print(f"\n{'='*60}")
        print(f"[2단계] 종료매물에서 재광고/결제 시작 ({len(property_numbers)}개)")
        print(f"{'='*60}")

        payment_results = {}
        failed_payments = {}

        for i, property_number in enumerate(property_numbers, 1):
            print(f"\n[재광고/결제 {i}/{len(property_numbers)}] 매물번호 {property_number}")
            if progress_callback:
                progress_callback(f"[2단계 {i}/{len(property_numbers)}] 매물 {property_number} 재광고/결제 중...")

            try:
                                                   
                await page.goto(self.ad_list_url, timeout=60000, wait_until='domcontentloaded')
                await page.wait_for_selector('table tbody tr', state='visible', timeout=30000)

                await page.evaluate()

                ad_end_button = await page.wait_for_selector('#wrap > div.container > div > div > div.sectionWrap > div.statusWrap.ver3 > div.statusItem.statusAdEnd.GTM_offerings_ad_list_end_ad', timeout=10000)
                await ad_end_button.click()

                await page.wait_for_selector('table tbody tr', state='visible', timeout=10000)

                await page.evaluate()

                await page.wait_for_timeout(3000)
                print(f"   ⏳ 종료매물 목록 서버 반영 대기 완료")

                result = await self.process_single_ended_property(page, property_number, popup_messages)
                if result[0]:      
                    payment_results[property_number] = result
                    print(f"   ✅ 결제 성공")
                else:
                                       
                    if result[1] == 'insufficient_balance':
                        print(f"\n{'='*60}")
                        print(f"💰 충전금이 부족하여 모든 처리를 중단합니다.")
                        print(f"   ⚠️ 충전 후 다시 시도해주세요.")
                        print(f"{'='*60}")

                        failed_payments[property_number] = {'reason': '충전금 부족', 'payment_status': 'insufficient_balance', 'no_retry': True}
                        for remaining_prop in property_numbers[i:]:
                            if remaining_prop != property_number:
                                failed_payments[remaining_prop] = {'reason': '충전금 부족으로 처리 중단', 'payment_status': 'insufficient_balance', 'no_retry': True}

                        break         

                    failed_payments[property_number] = {'reason': result[1], 'payment_status': result[1]}
                    print(f"   ❌ 결제 실패: {result[1]}")

            except Exception as e:
                failed_payments[property_number] = {'reason': str(e)}
                print(f"   ❌ 처리 중 오류: {e}")

            if i < len(property_numbers):
                await page.wait_for_timeout(1000)

        print(f"\n{'='*60}")
        print(f"[2단계 완료] 결제 성공: {len(payment_results)}개, 실패: {len(failed_payments)}개")
        print(f"{'='*60}")

        return payment_results, failed_payments

    async def process_single_ended_property(self, page, property_number, popup_messages):
        
        try:
                                       
            max_pages = 1
            try:
                total_count_element = await page.query_selector('#wrap > div.container > div > div > div.sectionWrap > div.statusWrap.ver3 > div.statusItem.statusAdEnd.GTM_offerings_ad_list_end_ad > span.cnt')
                if total_count_element:
                    total_count_text = await total_count_element.inner_text()
                    total_count = int(total_count_text.strip().replace(',', ''))
                    max_pages = (total_count + 49) // 50 + 1                    
                    print(f"   📊 종료매물: {total_count}개 → 최대 {max_pages}페이지까지 검색 (안전 마진 +1)")
                else:
                    print(f"   ⚠️ 종료매물 개수 확인 실패 - 최대 {max_pages}페이지까지 검색")
            except Exception as e:
                print(f"   ⚠️ 종료매물 개수 조회 실패: {e} - 최대 {max_pages}페이지까지 검색")

            property_found = False
            current_page = 1

            while not property_found and current_page <= max_pages:
                print(f"   📄 종료매물 {current_page}페이지에서 검색 중...")

                end_rows = await page.query_selector_all('#wrap > div.container > div > div > div.sectionWrap > div.singleSection.listSection > div.listWrap > table > tbody > tr')

                for row in end_rows:
                    number_cell = await row.query_selector('td:nth-child(3) > div.numberN')
                    if number_cell:
                        number_text = await number_cell.inner_text()
                        if property_number in number_text.strip():
                            print(f"   🎯 종료매물에서 매물번호 {property_number} 발견! ({current_page}페이지)")
                            property_found = True

                            try:
                                fullname_selectors = [
                                    'td.danjiName p.fullName span',
                                    'p.fullName span',
                                    '.fullName span'
                                ]
                                fullname = None
                                for selector in fullname_selectors:
                                    fullname_element = await row.query_selector(selector)
                                    if fullname_element:
                                        fullname_text = await fullname_element.inner_text()
                                        fullname = fullname_text.strip()
                                        if fullname:
                                            self.fullname_mapping[property_number] = fullname
                                            print(f"   🔖 fullName 저장: {property_number} → {fullname}")
                                            break
                                if not fullname:
                                    print(f"   ⚠️ fullName을 찾을 수 없음 (결제 실패 시 재시도 불가)")
                            except Exception as e:
                                print(f"   ⚠️ fullName 추출 실패: {e}")

                            await page.evaluate()

                            re_ad_button = await row.query_selector('a#reReg')
                            if re_ad_button:
                                await re_ad_button.click()
                                await page.wait_for_url('**/offerings/ad_regist', timeout=15000)

                                if not await self.process_ad_regist(page):
                                    return (False, "failed")

                                payment_success, payment_status = await self.process_payment(page, popup_messages)
                                if payment_success:
                                                                                       
                                    return (True, "success")
                                else:
                                    return (False, payment_status)
                            else:
                                print(f"   ❌ 재광고 버튼 없음")
                                return (False, "failed")

                if property_found:
                    break

                if current_page < max_pages:
                    print(f"   ⏭️  다음 페이지로 이동 중... ({current_page} → {current_page + 1})")
                    if not await self.goto_next_page_ended(page, current_page):
                        print(f"   ⚠️ 다음 페이지 이동 실패 - 검색 종료")
                        break
                    current_page += 1
                else:
                    break

            if not property_found:
                print(f"   ❌ 종료매물에서 찾을 수 없음 (총 {current_page}페이지 검색)")
                return (False, "not_found")

            return (False, "not_found")

        except Exception as e:
            return (False, str(e))

    async def find_saved_property_and_advertise(self, page, property_number):
        
        print(f"[saved 재시도] 일반 매물 리스트에서 fullName 매칭 매물 검색 중...")

        try:
                               
            saved_fullname = self.fullname_mapping.get(property_number)
            if not saved_fullname:
                print(f"   ❌ 저장된 fullName 없음 - 재시도 불가")
                print(f"   ℹ️ 광고등록 페이지까지 도달하지 못한 경우입니다.")
                return False

            print(f"   🔖 저장된 fullName: {saved_fullname}")
            print(f"   💡 fullName 매칭 + #naverAd 버튼으로 정확한 매물 찾기")

            await page.goto(self.ad_list_url, timeout=60000, wait_until='domcontentloaded')
            await page.wait_for_selector('table tbody tr', state='visible', timeout=30000)

            await page.evaluate()

            property_found = False
            current_page = 1

            while not property_found:
                print(f"   📄 {current_page}페이지에서 검색 중...")

                rows = await page.query_selector_all('table tbody tr')

                for row in rows:
                                         
                    ad_button = await row.query_selector('#naverAd')
                    if ad_button:
                                        
                        try:
                            fullname_selectors = [
                                'td.danjiName p.fullName span',
                                'td.danjiName > div > p.fullName > span',
                                'p.fullName span'
                            ]
                            current_fullname = None
                            for selector in fullname_selectors:
                                fullname_element = await row.query_selector(selector)
                                if fullname_element:
                                    fullname_text = await fullname_element.inner_text()
                                    current_fullname = fullname_text.strip()
                                    if current_fullname:
                                        break
                            
                            if current_fullname:
                                                
                                if current_fullname == saved_fullname:
                                    print(f"   🎯 fullName 매칭 성공: {current_fullname}")
                                    print(f"   ✅ 광고하기 버튼이 있는 정확한 매물 발견!")
                                    property_found = True

                                    await page.evaluate()

                                    await ad_button.click()
                                    await page.wait_for_timeout(1000)
                                    print(f"   ✅ 광고하기 버튼(#naverAd) 클릭 완료")

                                    print(f"   ⏳ 결제 페이지 로딩 대기 중...")
                                    await page.wait_for_selector('#consentMobile2', state='attached', timeout=15000)
                                    print(f"   ✅ 결제 페이지 이동 완료")

                                    return True
                                else:
                                    continue
                            else:
                                continue
                        except Exception as e:
                            print(f"   ⚠️ fullName 추출 실패: {e} - 다음 매물 검색")
                            continue

                if property_found:
                    break

                try:
                    next_button = await page.query_selector('.pagination a.btnArrow.next')
                    if next_button:
                        next_data_value = await next_button.get_attribute('data-value')
                        if next_data_value and int(next_data_value) <= current_page:
                            print("   마지막 페이지에 도달했습니다.")
                            break

                        await next_button.click()
                        await page.wait_for_timeout(2000)
                        await page.wait_for_selector('table tbody tr', timeout=15000)
                        current_page += 1
                    else:
                        break
                except:
                    break

            if not property_found:
                print(f"   ❌ fullName '{saved_fullname}'과 매칭되는 #naverAd 버튼 매물을 찾을 수 없습니다.")
                print(f"   ℹ️ 매물이 이미 광고 중이거나 종료된 상태일 수 있습니다.")
                return False

        except Exception as e:
            print(f"   ❌ fullName 매칭 매물 검색 중 오류: {e}")
            return False

    async def process_single_property_retry(self, page, property_number, popup_messages, progress_callback=None):
        
        print(f"\n{'='*50}")
        print(f"[재시도] 매물번호 {property_number} 처리 시작")
        print(f"{'='*50}")

        if progress_callback:
            progress_callback(f"[재시도] 매물번호 {property_number} 처리 시작")

        try:
                                         
            if progress_callback:
                progress_callback(f"[재시도] 매물번호 {property_number} 종료매물에서 검색 중...")

            re_register_result = await self.find_ended_property_and_re_register(page, property_number)
            if not re_register_result:
                return {'step': '종료매물 검색', 'reason': '종료매물에서 찾을 수 없거나 재광고 실패'}

            if progress_callback:
                progress_callback(f"[재시도] 매물번호 {property_number} 광고등록 처리 중...")

            if not await self.process_ad_regist(page):
                return {'step': '광고등록', 'reason': '광고등록 페이지 처리 실패'}

            if progress_callback:
                progress_callback(f"[재시도] 매물번호 {property_number} 결제 처리 중...")

            payment_success, payment_status = await self.process_payment(page, popup_messages)

            if payment_success:
                       
                print(f"  🎉 [재시도] 매물번호 {property_number} 실제 업데이트 완료!")
                if progress_callback:
                    progress_callback(f"[재시도] 매물번호 {property_number} 처리 완료!")
                print(f"  ✅ [재시도] 매물번호 {property_number} 처리 완료")

                try:
                    await page.goto(self.ad_list_url, timeout=10000, wait_until='domcontentloaded')
                    await page.wait_for_timeout(1000)
                    print("✅ 매물 리스트 페이지로 복귀 완료")
                except Exception as e:
                    print(f"⚠️ 목록 복귀 중 예외: {e} - 하지만 매물은 이미 성공적으로 처리되었습니다.")

                return True
            else:
                                            
                return {'step': '결제', 'reason': f'결제 처리 실패 - {payment_status}', 'payment_status': payment_status}

        except Exception as e:
            error_msg = f"[재시도] 매물번호 {property_number} 처리 중 오류 발생: {e}"
            if progress_callback:
                progress_callback(error_msg)
            print(error_msg)
            return {'step': '예외 발생', 'reason': str(e)}

    async def verify_properties_existence(self, page, property_numbers, progress_callback=None):
        
        print(f"\n{'='*60}")
        print(f"🔍 [사전 검증] 선택한 {len(property_numbers)}개 매물번호 존재 여부 확인")
        print(f"{'='*60}")

        if progress_callback:
            progress_callback(f"🔍 선택한 {len(property_numbers)}개 매물번호 존재 여부 확인 중...")

        found_properties = []             
        not_found_properties = []                

        try:
                            
            print("🌐 매물 리스트 페이지로 이동 중...")
            if progress_callback:
                progress_callback("🌐 매물 리스트 페이지로 이동 중...")

            await page.goto(self.ad_list_url, timeout=60000, wait_until='domcontentloaded')
            await page.wait_for_selector('table tbody tr', state='visible', timeout=30000)
            await page.wait_for_timeout(1500)

            await page.evaluate()

            all_property_numbers = []
            all_property_numbers_by_page = {}
            current_page = 1

            print(f"⏳ 1페이지 데이터 안정화 대기 중...")
            await page.wait_for_timeout(2000)

            while True:
                print(f"📄 {current_page}페이지 수집 중...")
                if progress_callback:
                    progress_callback(f"📄 {current_page}페이지 매물번호 수집 중...")

                await page.wait_for_timeout(1000)

                rows = await page.query_selector_all('#wrap > div.container > div > div > div.sectionWrap > div.singleSection.listSection > div.listWrap > table > tbody > tr')
                page_property_numbers = []
                rows_without_numberN = 0

                for row in rows:
                    try:
                        number_cell = await row.query_selector('td:nth-child(3) > div.numberN')
                        if number_cell:
                            number_text = await number_cell.inner_text()
                            number_stripped = number_text.strip()
                            if number_stripped:
                                page_property_numbers.append(number_stripped)
                                all_property_numbers.append(number_stripped)
                        else:
                            rows_without_numberN += 1
                    except Exception as e:
                        continue

                all_property_numbers_by_page[current_page] = page_property_numbers
                print(f"   전체 행: {len(rows)}개 / numberN 있음: {len(page_property_numbers)}개 / numberN 없음: {rows_without_numberN}개 (누적: {len(all_property_numbers)}개)")

                if not await self.goto_next_page(page, current_page):
                    print(f"✅ 마지막 페이지 도달 - 수집 완료 ({current_page}페이지)")
                    break
                current_page += 1

            total_properties_found = len(all_property_numbers)
            print(f"\n📊 전체 매물번호 수집 완료: {total_properties_found}개")

            try:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_filename = f"all_properties_{timestamp}.txt"
                with open(debug_filename, 'w', encoding='utf-8') as f:
                    f.write(f"=== 전체 매물번호 목록 ===\n")
                    f.write(f"수집 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"전체 매물 수: {total_properties_found}개\n")
                    f.write(f"페이지 수: {len(all_property_numbers_by_page)}페이지\n")
                    f.write(f"\n=== 페이지별 매물번호 ===\n")
                    for page_num, numbers in all_property_numbers_by_page.items():
                        f.write(f"\n[{page_num}페이지] ({len(numbers)}개)\n")
                        for num in numbers:
                            f.write(f"  {num}\n")
                    f.write(f"\n=== 선택한 매물번호 ({len(property_numbers)}개) ===\n")
                    for num in property_numbers:
                        status = "✅ 존재" if num in all_property_numbers else "❌ 미존재"
                        f.write(f"  {num} - {status}\n")
                print(f"📁 디버그 파일 저장: {debug_filename}")
                if progress_callback:
                    progress_callback(f"📁 디버그 파일 저장: {debug_filename}")
            except Exception as e:
                print(f"⚠️ 디버그 파일 저장 실패: {e}")

            for prop_num in property_numbers:
                if prop_num in all_property_numbers:
                    found_properties.append(prop_num)
                    for page_num, numbers in all_property_numbers_by_page.items():
                        if prop_num in numbers:
                            print(f"   ✅ 매물번호 {prop_num} 발견! ({page_num}페이지)")
                            if progress_callback:
                                progress_callback(f"   ✅ 매물 {prop_num} 발견 ({page_num}페이지)")
                            break
                else:
                    not_found_properties.append(prop_num)
                    print(f"   ❌ 매물번호 {prop_num} 미발견")

            print(f"\n{'='*60}")
            print(f"📊 [사전 검증 완료]")
            print(f"   📊 수집된 매물: {total_properties_found}개 ({current_page}페이지)")

            print(f"   ✅ 존재하는 매물: {len(found_properties)}개")
            if found_properties:
                print(f"      매물번호: {', '.join(found_properties)}")
            print(f"   ❌ 존재하지 않는 매물: {len(not_found_properties)}개")
            if not_found_properties:
                print(f"      매물번호: {', '.join(not_found_properties)}")
            print(f"{'='*60}")

            if progress_callback:
                progress_callback(f"📊 수집된 매물: {total_properties_found}개 ({current_page}페이지)")
                progress_callback(f"✅ 검증 완료: 존재 {len(found_properties)}개 / 미존재 {len(not_found_properties)}개")
                if not_found_properties:
                    progress_callback(f"⚠️ 미존재 매물: {', '.join(not_found_properties)}")

            return found_properties, not_found_properties

        except Exception as e:
            error_msg = f"❌ 매물번호 검증 중 오류: {e}"
            print(error_msg)
            if progress_callback:
                progress_callback(error_msg)
                                   
            return property_numbers, []

    async def run_automation(self, property_numbers, progress_callback=None):
        
        async with async_playwright() as p:
                                         
            if self.headless:
                browser = await p.chromium.launch(
                    headless=True,
                    slow_mo=50,                     
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--disable-images',                     
                        '--memory-pressure-off',             
                        '--max_old_space_size=4096',           
                        '--aggressive-cache-discard=false'          
                    ]
                )
            else:
                browser = await p.chromium.launch(
                    headless=False,
                    slow_mo=2000,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--start-maximized',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor'
                    ]
                )
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()

            popup_messages = []

            async def handle_global_popup(dialog):
                message = dialog.message
                popup_log = f"전역 팝업 감지: {dialog.type} - {message}"
                print(popup_log)
                             
                if progress_callback:
                    progress_callback(f"🔔 {popup_log}")

                popup_messages.append(message)
                try:
                    if dialog.type == 'alert':
                        await dialog.accept()
                        confirm_log = "Alert 팝업 확인됨"
                        print(confirm_log)
                        if progress_callback:
                            progress_callback(f"✅ {confirm_log}")
                    elif dialog.type == 'confirm':
                        await dialog.accept()
                        confirm_log = "Confirm 팝업 확인됨"
                        print(confirm_log)
                        if progress_callback:
                            progress_callback(f"✅ {confirm_log}")
                    elif dialog.type == 'prompt':
                        await dialog.accept("")
                        confirm_log = "Prompt 팝업 확인됨"
                        print(confirm_log)
                        if progress_callback:
                            progress_callback(f"✅ {confirm_log}")
                except Exception as e:
                    error_log = f"팝업 처리 중 오류: {e}"
                    print(error_log)
                    if progress_callback:
                        progress_callback(f"❌ {error_log}")

            page.on('dialog', handle_global_popup)

            try:
                                          
                original_total_count = len(property_numbers)

                if progress_callback:
                    progress_callback("로그인 중...")
                await self.login(page, popup_messages)

                verified_properties, not_found_properties = await self.verify_properties_existence(
                    page, property_numbers, progress_callback
                )

                if not_found_properties:
                    print(f"\n⚠️ {len(not_found_properties)}개 매물은 리스트에 존재하지 않아 처리에서 제외됩니다.")
                    if progress_callback:
                        progress_callback(f"⚠️ {len(not_found_properties)}개 매물 제외됨")

                property_numbers = verified_properties

                if not property_numbers:
                    print(f"\n❌ 처리 가능한 매물이 없습니다. 자동화를 종료합니다.")
                    if progress_callback:
                        progress_callback(f"❌ 처리 가능한 매물이 없습니다.")
                    return {
                        'success_count': 0,
                        'failed_properties': {prop: {'step': '사전 검증', 'reason': '매물 리스트에 존재하지 않음'} for prop in not_found_properties},
                        'total_count': len(not_found_properties)
                    }

                if progress_callback:
                    progress_callback(f"UPDATE_COUNT:{len(property_numbers)}")

                success_count = 0
                failed_properties = {}                                          

                for prop in not_found_properties:
                    failed_properties[prop] = {'step': '사전 검증', 'reason': '매물 리스트에 존재하지 않음'}

                successful_exposures, failed_exposures = await self.batch_end_exposure(
                    page, property_numbers, popup_messages, progress_callback
                )

                failed_properties.update(failed_exposures)

                if successful_exposures:
                    payment_results, failed_payments = await self.batch_process_ended_properties(
                        page, successful_exposures, popup_messages, progress_callback
                    )

                    success_count = len(payment_results)

                    failed_properties.update(failed_payments)
                else:
                    print("\n⚠️ 노출종료에 성공한 매물이 없어 2단계를 건너뜁니다.")

                retry_failed = {}                                          

                retryable_properties = {k: v for k, v in failed_properties.items() if not v.get('no_retry', False)}
                non_retryable_properties = {k: v for k, v in failed_properties.items() if v.get('no_retry', False)}

                retry_failed.update(non_retryable_properties)

                if non_retryable_properties:
                    print(f"\n{'='*60}")
                    print(f"⚠️  {len(non_retryable_properties)}개 매물은 재시도하지 않습니다 (로켓등록 아님):")
                    for prop_num in non_retryable_properties.keys():
                        print(f"  • 매물번호 {prop_num}")
                    print(f"{'='*60}")

                if retryable_properties:
                    print(f"\n{'='*60}")
                    print(f"🔄 실패한 {len(retryable_properties)}개 매물 재시도 중...")
                    print(f"{'='*60}")

                    if progress_callback:
                        progress_callback(f"🔄 실패한 {len(retryable_properties)}개 매물 재시도 중...")

                    for i, (property_number, fail_info) in enumerate(retryable_properties.items(), 1):
                        print(f"\n[재시도 {i}/{len(retryable_properties)}] 매물번호 {property_number}")
                        print(f"   1차 실패 원인: {fail_info.get('step', '알 수 없음')} - {fail_info.get('reason', '알 수 없음')}")
                        payment_status = fail_info.get('payment_status', 'failed')
                        print(f"   결제 상태: {payment_status}")
                        if progress_callback:
                            progress_callback(f"[재시도 {i}/{len(retryable_properties)}] 매물번호 {property_number}")

                        try:
                                                    
                            if payment_status == 'saved':
                                                                                                 
                                saved_fullname = self.fullname_mapping.get(property_number, '')
                                if saved_fullname:
                                    print(f"   📍 매물 저장됨 → fullName '{saved_fullname}' 매칭 + 광고하기 버튼으로 재시도")
                                else:
                                    print(f"   📍 매물 저장됨 → #naverAd 버튼으로 재시도 (fullName 없음)")

                                if not await self.find_saved_property_and_advertise(page, property_number):
                                    retry_failed[property_number] = {'step': '광고하기 검색', 'reason': 'fullName 매칭 매물을 찾을 수 없음'}
                                    msg = f"❌ 재시도 실패: {property_number} - fullName 매칭 매물을 찾을 수 없음"
                                    if progress_callback:
                                        progress_callback(msg)
                                    print(msg)
                                    continue

                                payment_success, payment_status = await self.process_payment(page, popup_messages)
                                if payment_success:
                                    success_count += 1
                                    msg = f"✅ 재시도 성공: {property_number} (saved → 결제 완료)"
                                    if progress_callback:
                                        progress_callback(msg)
                                    print(msg)

                                    await page.goto(self.ad_list_url, timeout=10000, wait_until='domcontentloaded')
                                    await page.wait_for_timeout(1000)
                                else:
                                                       
                                    if payment_status == 'insufficient_balance':
                                        print(f"\n{'='*60}")
                                        print(f"💰 충전금이 부족하여 재시도를 중단합니다.")
                                        print(f"   ⚠️ 충전 후 다시 시도해주세요.")
                                        print(f"{'='*60}")

                                        retry_failed[property_number] = {'step': '결제', 'reason': '충전금 부족', 'payment_status': 'insufficient_balance', 'no_retry': True}
                                        remaining_props = list(retryable_properties.keys())[i:]
                                        for remaining_prop in remaining_props:
                                            if remaining_prop != property_number:
                                                retry_failed[remaining_prop] = {'step': '재시도 중단', 'reason': '충전금 부족으로 처리 중단', 'payment_status': 'insufficient_balance', 'no_retry': True}
                                        break                

                                    retry_failed[property_number] = {'step': '결제', 'reason': f'결제 실패 - {payment_status}'}
                                    msg = f"❌ 재시도 실패: {property_number} - 결제 실패"
                                    if progress_callback:
                                        progress_callback(msg)
                                    print(msg)

                            else:
                                                        
                                fail_step = fail_info.get('step', 'failed')

                                if fail_step == '노출종료':
                                                                  
                                    print(f"   📍 노출종료 실패 → 매물 리스트에서 재시도")

                                    exposure_results, exposure_failed = await self.batch_end_exposure(
                                        page, [property_number], popup_messages, progress_callback
                                    )

                                    if property_number in exposure_results:
                                                             
                                        print(f"   ✅ 재시도 노출종료 성공 → 재광고/결제 진행")

                                        payment_results, payment_failed = await self.batch_process_ended_properties(
                                            page, [property_number], popup_messages, progress_callback
                                        )

                                        if property_number in payment_results:
                                            success_count += 1
                                            msg = f"✅ 재시도 성공: {property_number} (노출종료 재시도 → 결제 완료)"
                                            if progress_callback:
                                                progress_callback(msg)
                                            print(msg)
                                        else:
                                                   
                                            retry_failed[property_number] = payment_failed.get(property_number, {'step': '결제', 'reason': '재광고/결제 실패'})
                                            msg = f"❌ 재시도 실패: {property_number} - 재광고/결제 단계 실패"
                                            if progress_callback:
                                                progress_callback(msg)
                                            print(msg)
                                    else:
                                                      
                                        retry_failed[property_number] = exposure_failed.get(property_number, {'step': '노출종료', 'reason': '재시도 노출종료 실패'})
                                        msg = f"❌ 재시도 실패: {property_number} - 노출종료 재시도 실패"
                                        if progress_callback:
                                            progress_callback(msg)
                                        print(msg)
                                else:
                                                                 
                                    print(f"   📍 {fail_step} 실패 → 종료매물에서 재시도")
                                    result = await self.process_single_property_retry(page, property_number, popup_messages, progress_callback)
                                    if result is True:
                                        success_count += 1
                                        msg = f"✅ 재시도 성공: {property_number}"
                                        if progress_callback:
                                            progress_callback(msg)
                                        print(msg)
                                    else:
                                                           
                                        if isinstance(result, dict) and result.get('payment_status') == 'insufficient_balance':
                                            print(f"\n{'='*60}")
                                            print(f"💰 충전금이 부족하여 재시도를 중단합니다.")
                                            print(f"   ⚠️ 충전 후 다시 시도해주세요.")
                                            print(f"{'='*60}")

                                            retry_failed[property_number] = {'step': '결제', 'reason': '충전금 부족', 'payment_status': 'insufficient_balance', 'no_retry': True}
                                            remaining_props = list(retryable_properties.keys())[i:]
                                            for remaining_prop in remaining_props:
                                                if remaining_prop != property_number:
                                                    retry_failed[remaining_prop] = {'step': '재시도 중단', 'reason': '충전금 부족으로 처리 중단', 'payment_status': 'insufficient_balance', 'no_retry': True}
                                            break                

                                        if isinstance(result, dict):
                                            retry_failed[property_number] = result
                                            msg = f"❌ 재시도 실패: {property_number} - {result.get('step', '알 수 없음')}: {result.get('reason', '알 수 없음')}"
                                        else:
                                            retry_failed[property_number] = {'step': '알 수 없음', 'reason': '재시도 실패'}
                                            msg = f"❌ 재시도 실패: {property_number}"
                                        if progress_callback:
                                            progress_callback(msg)
                                        print(msg)
                        except Exception as e:
                            retry_failed[property_number] = {'step': '예외 발생', 'reason': str(e)}
                            msg = f"❌ 재시도 중 예외 발생: {property_number} - {e}"
                            if progress_callback:
                                progress_callback(msg)
                            print(msg)

                        if property_number in retry_failed:
                            try:
                                print("매물리스트 페이지로 복구 중...")
                                await page.goto(self.ad_list_url, timeout=20000, wait_until='domcontentloaded')
                                await page.wait_for_selector('table tbody tr', state='visible', timeout=10000)
                                print("매물리스트 페이지 복구 완료")
                            except Exception as e:
                                print(f"매물리스트 페이지 복구 실패: {e}")

                        if i < len(retryable_properties):
                            print("다음 재시도 매물 처리를 위해 대기 중...")
                            await page.wait_for_timeout(2000)

                final_msg = f"전체 완료! 성공: {success_count}개, 최종 실패: {len(retry_failed)}개"
                if progress_callback:
                    progress_callback(final_msg)

                print(f"\n{'='*60}")
                print(f"📊 전체 자동화 프로세스 완료!")
                print(f"총 선택 매물: {original_total_count}개")
                print(f"✅ 최종 성공: {success_count}개")
                print(f"❌ 최종 실패: {len(retry_failed)}개")

                if retry_failed:
                    print(f"\n{'='*60}")
                    print("❌ 실패 상세 정보:")
                    print(f"{'='*60}")
                    for prop_num, fail_info in retry_failed.items():
                        step = fail_info.get('step', '알 수 없음')
                        reason = fail_info.get('reason', '알 수 없음')
                        print(f"  • 매물번호 {prop_num}")
                        print(f"    └─ 실패 단계: {step}")
                        print(f"    └─ 실패 원인: {reason}")
                else:
                    print("🎉 모든 매물 처리 완료!")
                print(f"{'='*60}")

                await page.wait_for_timeout(1500)              

                return {
                    'success_count': success_count,
                    'failed_properties': retry_failed,                                                  
                    'total_count': original_total_count                
                }

            except Exception as e:
                error_msg = f"자동화 프로세스 중 전체 오류 발생: {e}"
                if progress_callback:
                    progress_callback(error_msg)
                print(error_msg)
                return None
            finally:
                            
                page.remove_listener('dialog', handle_global_popup)

                if self.headless:
                    await browser.close()
                else:
                    print("\n⚠️  브라우저를 수동으로 닫아주세요 (디버깅 모드)")

if __name__ == '__main__':
    async def _main():
        props_env = os.getenv('PROPERTY_NUMBERS', '')
        props = [p.strip() for p in props_env.split(',') if p.strip()]
        if not props and os.path.exists('data/scheduled_properties.json'):
            try:
                with open('data/scheduled_properties.json', 'r', encoding='utf-8') as sf:
                    props = json.load(sf).get('properties', [])
            except Exception:
                pass
        if not props:
            print('❌ 처리할 매물번호가 없습니다.')
            return
        automation = RealEstateAutomation(headless=True)
        await automation.run_automation(props)
    asyncio.run(_main())

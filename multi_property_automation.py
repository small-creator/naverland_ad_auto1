import asyncio
import os
import sys
import json
from datetime import datetime
from property_updater import RealEstateAutomation

async def get_target_properties():
    props_str = os.getenv('PROPERTY_NUMBERS', '').strip()
    if props_str:
        props = [p.strip() for p in props_str.split(',') if p.strip()]
        if props:
            return props, 'manual_env'

    scheduled_file = os.path.join('data', 'scheduled_properties.json')
    if os.path.exists(scheduled_file):
        try:
            with open(scheduled_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                props = [str(p).strip() for p in data.get('properties', []) if str(p).strip()]
                if props:
                    return props, 'scheduled_file'
        except Exception as e:
            print(f"예약 파일 읽기 실패: {e}")

    member_id = os.getenv('MEMBER_ID', '').strip()
    if not member_id and os.path.exists('config.json'):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                member_id = json.load(f).get('member_id', '').strip()
        except Exception:
            pass

    if member_id:
        try:
            from logic_handler import run_real_logic
            print(f"회원 ID '{member_id}'의 광고 매물 순위를 분석하여 업데이트 대상 매물을 자동 조회합니다...")
            all_rank_items = await run_real_logic(member_id, print, test_mode=False)
            auto_props = [
                str(item['article_no']).strip() for item in all_rank_items
                if item.get('update_needed') and item.get('article_no')
            ]
            if auto_props:
                print(f"순위 분석 결과 업데이트 필요 매물 {len(auto_props)}개 자동 감지")
                return auto_props, 'auto_detected'
            else:
                print("순위 분석 결과 현재 업데이트가 필요한 매물이 없습니다.")
        except Exception as e:
            print(f"네이버 부동산 매물 순위 자동 조회 중 예외 발생: {e}")

    return [], 'none'

async def main():
    login_id = os.getenv('LOGIN_ID', '')
    login_pw = os.getenv('LOGIN_PASSWORD', '')

    if not login_id or not login_pw:
        if os.path.exists('config.json'):
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    login_id = login_id or cfg.get('ai_partner_login_id', '')
                    login_pw = login_pw or cfg.get('ai_partner_password', '')
            except Exception:
                pass

    if not login_id or not login_pw:
        print("❌ 로그인 실패로 자동화 중단")
        print("아이디 또는 비밀번호가 설정되지 않았습니다.")
        sys.exit(1)

    print("=" * 60)
    print("🚀 다중 매물 광고 업데이트 자동화 프로세스 시작")
    print(f"🔧 로그인 ID: {login_id}")
    print("=" * 60)

    properties, source = await get_target_properties()

    test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'
    if test_mode:
        print("🧪 테스트 모드 활성화")
        if properties:
            properties = properties[:2]

    if not properties:
        print("❌ 처리할 매물번호가 없습니다")
        sys.exit(0)

    print(f"📋 대상 매물 ({source}): {len(properties)}개 -> {', '.join(properties)}")

    automation = RealEstateAutomation(headless=True)
    automation.login_id = login_id
    automation.login_pw = login_pw

    try:
        results = await automation.run_automation(properties)
        if not results:
            print("❌ 자동화 실행 실패: 결과 객체가 비어있습니다.")
            sys.exit(1)

        success_count = results.get('success_count', 0)
        total_count = results.get('total_count', len(properties))
        failed_dict = results.get('failed_properties', {})

        print("\n" + "=" * 60)
        print("📊 최종 실행 결과 요약")
        print(f"✅ 최종 성공: {success_count}/{total_count}개")

        if failed_dict:
            failed_props = list(failed_dict.keys())
            print(f"❌ 최종 실패: {', '.join(failed_props)}")

            exposure_failed = []
            saved_failed = []
            insufficient_failed = []
            payment_failed = []

            for p_num, fail_data in failed_dict.items():
                step = fail_data.get('step', '')
                reason = fail_data.get('reason', '')
                p_status = fail_data.get('payment_status', '')

                if p_status == 'insufficient_balance' or '충전금' in reason:
                    insufficient_failed.append(p_num)
                elif '노출' in step or '종료' in step:
                    exposure_failed.append(p_num)
                elif '저장' in step or '저장' in reason:
                    saved_failed.append(p_num)
                elif '결제' in step or '결제' in reason:
                    payment_failed.append(p_num)
                else:
                    payment_failed.append(p_num)

            if exposure_failed:
                print(f"📋 노출종료 실패: {', '.join(exposure_failed)}")
            if saved_failed:
                print(f"📝 광고 저장됨(결제안됨): {', '.join(saved_failed)}")
            if insufficient_failed:
                print(f"💰 충전금 부족: {', '.join(insufficient_failed)}")
            if payment_failed:
                print(f"💳 결제 실패: {', '.join(payment_failed)}")
        else:
            print("🎉 모든 대상 매물의 광고 업데이트가 성공적으로 완료되었습니다!")

        print("=" * 60)

    except Exception as e:
        print(f"❌ 자동화 실행 실패: {e}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())

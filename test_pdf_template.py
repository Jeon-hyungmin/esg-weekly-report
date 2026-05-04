"""PDF 양식 테스트 - Claude API / 이메일 없이 샘플 데이터로 PDF만 생성"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

from generate_and_send_report import build_pdf, get_week_info

SAMPLE = {
    "summary": {
        "policy": "K-ESG 가이드라인 2.0 개정안 — 환경부, 2026.06 시행 예정, 전 업종 적용",
        "environment": "탄소중립 기술 로드맵 발표 — 산업부, 2030 목표 재설정",
        "social": "공급망 실사법 시행령 입법예고 — 법무부, 500인 이상 사업장 우선 적용",
        "governance": "ESG 공시 의무화 1단계 시행 — 금융위, 자산 2조 원 이상 상장사 대상",
        "global": "EU CSRD 이행 가이드라인 확정 — 한국 수출기업 대응 시급",
        "key_points": [
            "K-ESG 2.0 개정으로 평가 지표 확대, 중소기업도 단계적 적용 예정",
            "ESG 공시 의무화 본격화 — 2026년 대기업, 2028년 중견기업으로 확대",
            "EU CSRD 수출기업 영향 — 협력사 ESG 데이터 요구 증가"
        ]
    },
    "section01": [
        {
            "star": True,
            "title": "K-ESG 가이드라인 2.0 개정안 행정예고",
            "issuer": "환경부·산업부 공동",
            "date": "2026.04.28",
            "stage": "입법예고",
            "target": "전 업종 (중소기업 단계적 적용)",
            "source_name": "환경부 보도자료",
            "source_url": "https://www.me.go.kr",
            "points": [
                "기존 61개 지표에서 78개로 확대, 공급망·생물다양성 항목 신설",
                "중요 키워드: 공급망 실사, 생물다양성 공시가 핵심 추가 항목",
                "2026년 하반기 최종 확정 후 2027년부터 단계적 적용"
            ]
        },
        {
            "star": False,
            "title": "탄소중립 산업 전환 지원 패키지 발표",
            "issuer": "산업통상자원부",
            "date": "2026.04.30",
            "stage": "확정",
            "target": "",
            "source_name": "산업통상자원부 보도자료",
            "source_url": "https://www.motie.go.kr",
            "points": [
                "철강·화학·시멘트 등 고탄소 업종 전환 자금 3조 원 지원",
                "2030년까지 탄소 집약도 40% 감축 목표 설정"
            ]
        },
        {
            "star": False,
            "title": "ESG 공시 표준 세부 지침 의견수렴",
            "issuer": "금융위원회",
            "date": "2026.05.02",
            "stage": "의견수렴",
            "target": "자산 2조 원 이상 코스피 상장사",
            "source_name": "금융위원회 보도자료",
            "source_url": "https://www.fsc.go.kr",
            "points": [
                "기후 관련 공시(TCFD 기반) 의무화, 2026회계연도부터 적용",
                "Scope 3 온실가스 배출량 공시는 2027년 유예"
            ]
        }
    ],
    "section02": [
        {
            "headline": "\"ESG 경영, 이제는 생존의 문제\"…중소기업 10곳 중 7곳 준비 미흡",
            "media": "한국경제",
            "date": "2026.05.01",
            "source_url": "https://www.hankyung.com",
            "points": [
                "중소기업중앙회 조사: 중소기업 72% ESG 대응 체계 미구축",
                "공급망 실사 의무화 앞두고 협력사 ESG 역량 강화 시급",
                "시사점: S&C 같은 ESG 경영지도 전문기관 수요 급증 예상"
            ]
        },
        {
            "headline": "EU 탄소국경조정제도(CBAM), 한국 수출기업 연간 3,200억 추가 부담",
            "media": "매일경제",
            "date": "2026.04.29",
            "source_url": "https://www.mk.co.kr",
            "points": [
                "2026년 본격 과금 시작, 철강·알루미늄·비료 등 6대 품목 영향",
                "국내 수출기업 Scope 1·2 탄소 인증 서류 준비 필수"
            ]
        },
        {
            "headline": "ESG 경영지도사 자격 수요 급증…중소기업 ESG 컨설팅 시장 2배 성장",
            "media": "이투데이",
            "date": "2026.04.30",
            "source_url": "https://www.etoday.co.kr",
            "points": [
                "ESG 공시 의무화 앞두고 컨설팅·경영지도 전문인력 수요 폭증",
                "시사점: ESG 경영지도 전문 사무소의 시장 선점 기회 확대"
            ]
        }
    ],
    "section03": {
        "large": [
            {"company": "삼성전자",   "area": "E", "activity": "2030 RE100 달성 계획 공시, 국내 사업장 재생에너지 전환율 45% 달성"},
            {"company": "SK하이닉스", "area": "S", "activity": "협력사 ESG 역량 강화 프로그램 확대, 1·2차 협력사 500개사 대상"},
            {"company": "현대자동차", "area": "G", "activity": "ESG 위원회 독립성 강화, 사외이사 과반수 구성 및 ESG 보수 연동"}
        ],
        "sme": [
            "제조업/친환경 포장재 기업: 탄소발자국 인증 취득으로 대기업 납품 자격 획득",
            "IT서비스/중견기업: ESG 경영보고서 첫 발간, 이해관계자 소통 강화"
        ]
    },
    "section04": {
        "short_term": [
            "K-ESG 2.0 개정안 주요 변경 지표 파악 및 자체 점검표 업데이트",
            "공급망 실사 의무화 일정 확인 및 고객사 대응 컨설팅 방안 준비",
            "ESG 공시 의무화 대상 기업 현황 파악, 공시 지원 서비스 설계"
        ],
        "mid_term": [
            "TCFD 기반 기후 공시 작성 실무 역량 강화 (시나리오 분석 포함)",
            "생물다양성 공시(TNFD) 기초 개념 학습 및 국내 적용 사례 연구",
            "EU CSRD 이중 중요성 평가(DMA) 방법론 습득"
        ],
        "practical": [
            "K-ESG 2.0 개정안 신규 항목에 맞춘 경영지도 진단 도구 개발",
            "이번 주 주요 정책 변화를 반영한 ESG 컨설팅 체크리스트 업데이트"
        ],
        "sc_e": "탄소중립 정책 흐름을 반영해 고객사의 온실가스 감축 로드맵 수립 지원 컨설팅 강화",
        "sc_s": "공급망 실사 의무화 대응을 위한 협력사 ESG 실사 체계 구축 지원 서비스 개발",
        "sc_g": "ESG 공시 의무화에 대비한 이사회 운영·공시 체계 정비 컨설팅 패키지 설계",
        "sc_idea": "K-ESG 2.0 기반 맞춤형 진단 → 개선 계획 수립 → 이행 모니터링 원스톱 경영지도 패키지 출시"
    },
    "section05": {
        "short_term": [
            "K-ESG 2.0 최종안 확정 및 업종별 적용 기준 발표 예상",
            "금융위 ESG 공시 세부 지침 의견수렴 종료 후 확정",
            "EU CBAM 과금 첫 분기 보고서 제출 (한국 수출기업)"
        ],
        "mid_term": [
            "공급망 실사법 시행령 확정, 대기업 협력사 ESG 요구 본격화",
            "ESG 평가 기관 간 통합 기준 논의 가속화",
            "사회복지시설 ESG 자가진단 시범 사업 실시 전망"
        ],
        "long_term": [
            "ESG 공시 의무화 전 업종 확대 (2030년 중소기업까지)",
            "탄소중립 2050 이행 점검 강화로 기업 감축 압력 심화",
            "ESG 경영 내재화 수준이 기업 신용등급 직결되는 구조 정착"
        ],
        "expert_view": "이번 주 핵심은 'ESG의 일상화'입니다. K-ESG 2.0 개정과 공시 의무화가 맞물리며 ESG는 선택이 아닌 규정 준수의 영역으로 진입했습니다. 특히 공급망 실사 의무화는 중소기업에도 ESG 역량이 생존 조건이 됨을 의미합니다. S&C는 이 전환점에서 제도 변화를 선제적으로 해석하고, 고객사가 규정을 넘어 ESG를 경쟁력으로 전환하도록 이끄는 전문 경영지도 파트너로 포지셔닝해야 합니다.",
        "next_issue": [
            "K-ESG 2.0 신규 지표 심층 분석 및 업종별 대응 전략",
            "공급망 실사 의무화 대비 협력사 ESG 평가 방법론",
            "ESG 공시 의무화 1단계 기업 사례 분석 및 시사점"
        ]
    }
}

if __name__ == "__main__":
    week_label, date_display, vol_str, date_range, week_num, next_label = get_week_info()
    out = Path(f"ESG_주간동향리포트_{week_label}_TEST.pdf")
    print(f"PDF 생성 중: {out}")
    build_pdf(SAMPLE, out, week_label, date_display, vol_str, date_range, week_num, next_label)
    print(f"완료: {out}")

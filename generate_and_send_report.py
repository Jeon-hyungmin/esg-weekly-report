import getpass
import json
import os
import re
import smtplib
import sys
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from google import genai
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, KeepTogether, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ── Brand colors ───────────────────────────────────────────────────────────────
C_OLIVE      = colors.HexColor("#4A5C3A")
C_OLIVE_MID  = colors.HexColor("#5B7A4A")
C_BEIGE_BG   = colors.HexColor("#F5F0E6")
C_BEIGE_BOX  = colors.HexColor("#EDE8DC")
C_ORANGE     = colors.HexColor("#C96A2A")
C_BLUE_SLATE = colors.HexColor("#4A6B8A")
C_BROWN      = colors.HexColor("#7A5C3A")
C_DARK       = colors.HexColor("#2C2C2C")
C_DARK_BOX   = colors.HexColor("#333333")
C_GOLD       = colors.HexColor("#C9A84C")
C_GRAY       = colors.HexColor("#888888")
C_LINE       = colors.HexColor("#C8C0B0")
C_WHITE      = colors.white

FONT_REG  = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


# ── Font setup ─────────────────────────────────────────────────────────────────
def find_korean_font() -> None:
    global FONT_REG, FONT_BOLD
    candidates = [
        ("MalgunGothic",  "MalgunGothicBold",
         Path("C:/Windows/Fonts/malgun.ttf"),
         Path("C:/Windows/Fonts/malgunbd.ttf")),
        ("NanumGothic", "NanumGothicBold",
         Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
         Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf")),
    ]
    for reg, bold, rp, bp in candidates:
        if rp.exists():
            pdfmetrics.registerFont(TTFont(reg, str(rp)))
            FONT_REG = reg
            if bp.exists():
                pdfmetrics.registerFont(TTFont(bold, str(bp)))
                FONT_BOLD = bold
            else:
                FONT_BOLD = reg
            return


# ── Week metadata ──────────────────────────────────────────────────────────────
def get_week_info():
    now = datetime.now()
    wn = (now.day - 1) // 7 + 1
    week_label = f"{now.year}-{now.month:02d}-W{wn}"
    days_ko = ["월", "화", "수", "목", "금", "토", "일"]
    date_display = f"{now.year}년 {now.month:02d}월 {now.day:02d}일 ({days_ko[now.weekday()]})"
    vol_str = f"VOL. {now.year}-{now.month:02d}  |  {wn}th WEEK"
    monday = now - timedelta(days=now.weekday())
    friday = monday + timedelta(days=4)
    date_range = f"{monday.strftime('%Y.%m.%d')} ~ {friday.strftime('%Y.%m.%d')}"
    next_week = wn + 1 if wn < 5 else 1
    next_month = now.month if wn < 5 else (now.month % 12 + 1)
    next_year  = now.year if next_month > 1 or wn < 5 else now.year + 1
    next_label = f"{next_year}년 {next_month:02d}월 {next_week}주차"
    return week_label, date_display, vol_str, date_range, wn, next_label


# ── Gemini API ─────────────────────────────────────────────────────────────────
def generate_esg_report(week_label: str, date_range: str, api_key: str) -> dict:
    client = genai.Client(api_key=api_key)
    prompt = f"""당신은 S&C 행정사 사무소의 ESG 경영지도 심사위원입니다.
검색기간 {date_range} ({week_label}) 기준 ESG 주간 동향 리포트를 작성해주세요.
이 리포트는 ESG 경영지도 심사위원 활동을 위한 자료로, 국내외 ESG 정책·기업·시장 동향을 전문적으로 다룹니다.
특정 업종에 한정하지 말고 ESG 경영 전반에 걸친 내용으로 작성하세요.

source_url은 발표 기관의 공식 사이트 또는 보도자료·입법예고 페이지 URL을 기재하세요.
예) 환경부→https://www.me.go.kr, 금융위→https://www.fsc.go.kr, 산업부→https://www.motie.go.kr,
    국회→https://likms.assembly.go.kr, 법제처→https://www.law.go.kr, 한국경제→https://www.hankyung.com
언론 source_url은 해당 매체의 공식 홈페이지 주소를 사용하세요.

순수 JSON만 응답하세요 (``` 불필요):

{{
  "summary": {{
    "policy": "정책 핵심 이슈명 — 한 줄 요약(발표주체·시행시기 포함)",
    "environment": "환경 이슈 — 한 줄 요약",
    "social": "사회 이슈 — 한 줄 요약",
    "governance": "지배구조 이슈 — 한 줄 요약",
    "global": "글로벌 이슈 — 한 줄 요약",
    "key_points": ["핵심 내용 1", "핵심 내용 2", "핵심 내용 3"]
  }},
  "section01": [
    {{
      "star": true,
      "title": "핵심 정책명",
      "issuer": "기관명",
      "date": "YYYY.MM.DD",
      "stage": "입법예고",
      "target": "적용 대상",
      "source_name": "출처 사이트명 (예: 환경부 보도자료)",
      "source_url": "https://www.me.go.kr (발표 기관 공식 사이트 또는 보도자료 URL)",
      "points": ["핵심 내용 1", "핵심 내용 2", "핵심 내용 3"]
    }},
    {{
      "star": false,
      "title": "정책명 2",
      "issuer": "기관명",
      "date": "YYYY.MM.DD",
      "stage": "",
      "target": "",
      "source_name": "출처 사이트명",
      "source_url": "https://발표기관공식사이트",
      "points": ["내용 1", "내용 2"]
    }},
    {{
      "star": false,
      "title": "정책명 3",
      "issuer": "기관명",
      "date": "YYYY.MM.DD",
      "stage": "",
      "target": "",
      "source_name": "출처 사이트명",
      "source_url": "https://발표기관공식사이트",
      "points": ["내용 1", "내용 2"]
    }}
  ],
  "section02": [
    {{"headline": "기사 제목", "media": "매체명", "date": "YYYY.MM.DD", "source_url": "https://매체공식사이트", "points": ["메시지 1", "메시지 2", "시사점"]}},
    {{"headline": "기사 제목", "media": "매체명", "date": "YYYY.MM.DD", "source_url": "https://매체공식사이트", "points": ["메시지 1", "메시지 2"]}},
    {{"headline": "기사 제목", "media": "매체명", "date": "YYYY.MM.DD", "source_url": "https://매체공식사이트", "points": ["메시지", "시사점"]}}
  ],
  "section03": {{
    "large": [
      {{"company": "기업명", "area": "E", "activity": "주요 활동 내용"}},
      {{"company": "기업명", "area": "S", "activity": "주요 활동 내용"}},
      {{"company": "기업명", "area": "G", "activity": "주요 활동 내용"}}
    ],
    "sme": ["업종/기업명: 주요 활동 1", "업종/기업명: 주요 활동 2"]
  }},
  "section04": {{
    "short_term": ["ESG 경영지도 심사위원 관점의 단기 점검 항목 1", "점검 항목 2", "점검 항목 3"],
    "mid_term": ["ESG 경영지도 역량 강화를 위한 중기 학습 항목 1", "학습 항목 2", "학습 항목 3"],
    "practical": ["심사 실무 준비 항목 1", "실무 항목 2"],
    "sc_e": "이번 주 환경(E) 이슈를 ESG 경영지도 컨설팅에 활용하는 방안",
    "sc_s": "이번 주 사회(S) 이슈를 ESG 경영지도 컨설팅에 활용하는 방안",
    "sc_g": "이번 주 지배구조(G) 이슈를 ESG 경영지도 컨설팅에 활용하는 방안",
    "sc_idea": "S&C 경영지도 사업에 즉시 활용 가능한 아이디어 한 줄"
  }},
  "section05": {{
    "short_term": ["단기 전망 1", "단기 전망 2", "단기 전망 3"],
    "mid_term": ["중기 전망 1", "중기 전망 2", "중기 전망 3"],
    "long_term": ["장기 전망 1", "장기 전망 2", "장기 전망 3"],
    "expert_view": "이번 주 이슈를 종합한 심사위원 관점의 핵심 인사이트",
    "next_issue": ["예고 주제 1", "예고 주제 2", "예고 주제 3"]
  }}
}}"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    text = response.text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    return json.loads(text)


# ── Style factory ──────────────────────────────────────────────────────────────
def styles() -> dict:
    def ps(name, **kw):
        font = kw.pop("font", FONT_REG)
        return ParagraphStyle(name, fontName=font, **kw)

    return {
        "brand":        ps("brand",        font=FONT_BOLD, fontSize=7,  textColor=C_OLIVE,   leading=10),
        "brand_sub":    ps("brand_sub",                    fontSize=7,  textColor=C_GRAY,    leading=10),
        "vol":          ps("vol",                          fontSize=8,  textColor=C_DARK,    leading=11, alignment=2),
        "date_big":     ps("date_big",     font=FONT_BOLD, fontSize=10, textColor=C_DARK,    leading=13, alignment=2),
        "title_esg":    ps("title_esg",    font=FONT_BOLD, fontSize=26, textColor=C_OLIVE,   leading=32),
        "title_week":   ps("title_week",   font=FONT_BOLD, fontSize=26, textColor=C_DARK,    leading=32),
        "subtitle":     ps("subtitle",                     fontSize=9,  textColor=C_DARK,    leading=14),
        "meta":         ps("meta",                         fontSize=8,  textColor=C_DARK,    leading=12),
        "meta_bold":    ps("meta_bold",    font=FONT_BOLD, fontSize=8,  textColor=C_DARK,    leading=12),
        "sec_num":      ps("sec_num",      font=FONT_BOLD, fontSize=18, textColor=C_OLIVE,   leading=22),
        "sec_title":    ps("sec_title",    font=FONT_BOLD, fontSize=13, textColor=C_DARK,    leading=17),
        "sec_sub":      ps("sec_sub",                      fontSize=8,  textColor=C_GRAY,    leading=11, alignment=2),
        "policy_star":  ps("policy_star",  font=FONT_BOLD, fontSize=11, textColor=C_DARK,    leading=15),
        "policy_title": ps("policy_title", font=FONT_BOLD, fontSize=10, textColor=C_DARK,    leading=13),
        "body":         ps("body",                         fontSize=9,  textColor=C_DARK,    leading=14),
        "bullet":       ps("bullet",                       fontSize=9,  textColor=C_DARK,    leading=14, leftIndent=10),
        "news_title":   ps("news_title",   font=FONT_BOLD, fontSize=10, textColor=C_DARK,    leading=14),
        "news_src":     ps("news_src",                     fontSize=8,  textColor=C_GRAY,    leading=11),
        "news_bullet":  ps("news_bullet",                  fontSize=8,  textColor=C_DARK,    leading=13, leftIndent=8),
        "tbl_hdr":      ps("tbl_hdr",      font=FONT_BOLD, fontSize=9,  textColor=C_WHITE,   leading=12),
        "tbl_co":       ps("tbl_co",       font=FONT_BOLD, fontSize=9,  textColor=C_OLIVE,   leading=12),
        "tbl_body":     ps("tbl_body",                     fontSize=8,  textColor=C_DARK,    leading=12),
        "chk_hdr":      ps("chk_hdr",      font=FONT_BOLD, fontSize=9,  textColor=C_WHITE,   leading=12),
        "chk_item":     ps("chk_item",                     fontSize=9,  textColor=C_DARK,    leading=14),
        "sc_label":     ps("sc_label",     font=FONT_BOLD, fontSize=8,  textColor=C_OLIVE,   leading=12),
        "sc_body":      ps("sc_body",                      fontSize=8,  textColor=C_DARK,    leading=12),
        "sc_idea":      ps("sc_idea",                      fontSize=8,  textColor=C_DARK,    leading=12),
        "out_sub":      ps("out_sub",                      fontSize=7,  textColor=C_GRAY,    leading=10),
        "out_hdr":      ps("out_hdr",      font=FONT_BOLD, fontSize=10, textColor=C_DARK,    leading=13),
        "out_item":     ps("out_item",                     fontSize=8,  textColor=C_DARK,    leading=13),
        "expert":       ps("expert",                       fontSize=10, textColor=C_WHITE,   leading=16),
        "next_hdr":     ps("next_hdr",     font=FONT_BOLD, fontSize=9,  textColor=C_GOLD,    leading=13),
        "next_item":    ps("next_item",                    fontSize=9,  textColor=C_WHITE,   leading=13),
        "footer_brand": ps("footer_brand", font=FONT_BOLD, fontSize=8,  textColor=C_OLIVE,   leading=12, alignment=1),
        "footer_body":  ps("footer_body",                  fontSize=7,  textColor=C_GRAY,    leading=11, alignment=1),
        "badge_txt":    ps("badge_txt",    font=FONT_BOLD, fontSize=8,  textColor=C_WHITE,   leading=10),
        "badge_cont":   ps("badge_cont",                   fontSize=8,  textColor=C_DARK,    leading=12),
        "kp_label":     ps("kp_label",     font=FONT_BOLD, fontSize=8,  textColor=C_WHITE,   leading=11),
        "kp_bullet":    ps("kp_bullet",                    fontSize=9,  textColor=C_DARK,    leading=14, leftIndent=8),
        "src_link":     ps("src_link",                     fontSize=8,  textColor=C_BLUE_SLATE, leading=12),
    }


# ── Helper: section header row ─────────────────────────────────────────────────
def section_header(num: str, title: str, sub: str, S: dict):
    data = [[
        Paragraph(num, S["sec_num"]),
        Paragraph(title, S["sec_title"]),
        Paragraph(sub, S["sec_sub"]),
    ]]
    t = Table(data, colWidths=[14*mm, 100*mm, None])
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "BOTTOM"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("TOPPADDING", (0,0), (-1,-1), 0),
    ]))
    return [
        t,
        HRFlowable(width="100%", thickness=1.5, color=C_OLIVE, spaceAfter=6),
    ]


# ── Helper: olive left-bar box ─────────────────────────────────────────────────
def left_bar_box(content_rows, bar_color=C_OLIVE_MID):
    inner = Table([[r] for r in content_rows],
                  colWidths=[PAGE_W - MARGIN*2 - 6*mm])
    inner.setStyle(TableStyle([
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
    ]))
    outer = Table([[inner]], colWidths=[PAGE_W - MARGIN*2])
    outer.setStyle(TableStyle([
        ("LEFTPADDING",   (0,0), (0,0), 0),
        ("RIGHTPADDING",  (0,0), (0,0), 0),
        ("TOPPADDING",    (0,0), (0,0), 0),
        ("BOTTOMPADDING", (0,0), (0,0), 0),
        ("LINEBEFORE",    (0,0), (0,0), 4, bar_color),
        ("BACKGROUND",    (0,0), (0,0), C_BEIGE_BG),
    ]))
    return outer


# ── PDF builder ────────────────────────────────────────────────────────────────
def build_pdf(data: dict, output_path: Path,
              week_label: str, date_display: str,
              vol_str: str, date_range: str,
              week_num: int, next_label: str) -> None:

    find_korean_font()
    S = styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )
    story = []
    inner_w = PAGE_W - MARGIN * 2

    # ── HEADER ────────────────────────────────────────────────────────────────
    hdr = Table([[
        Table([
            [Paragraph("SAFE &amp; CARE SOLUTION", S["brand"])],
            [Paragraph("S&amp;C 행정사 사무소 · ESG 경영지도", S["brand_sub"])],
        ], colWidths=[inner_w * 0.6]),
        Table([
            [Paragraph(vol_str, S["vol"])],
            [Paragraph(date_display, S["date_big"])],
        ], colWidths=[inner_w * 0.4]),
    ]], colWidths=[inner_w * 0.6, inner_w * 0.4])
    hdr.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 4*mm))

    # ── TITLE ─────────────────────────────────────────────────────────────────
    title_row = Table([[
        Paragraph("ESG 주간동향", S["title_esg"]),
        Paragraph(" 리포트", S["title_week"]),
    ]], colWidths=[inner_w * 0.55, inner_w * 0.45])
    title_row.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "BOTTOM"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
    ]))
    story.append(title_row)
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("한 주간의 ESG 정책·언론·기업 동향을 한 권에 모았습니다.", S["subtitle"]))
    story.append(Paragraph("심사위원의 시선으로 정리한 인사이트를 담습니다.", S["subtitle"]))
    story.append(Spacer(1, 3*mm))

    # meta line
    meta_parts = [
        Paragraph(f"검색기간  {date_range}", S["meta"]),
        Paragraph("작성  전형민 총괄관리자", S["meta_bold"]),
        Paragraph("구분  내부 참고자료", S["meta"]),
    ]
    meta_row = Table([meta_parts], colWidths=[inner_w*0.38, inner_w*0.34, inner_w*0.28])
    meta_row.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(meta_row)
    story.append(Spacer(1, 4*mm))

    # ── SUMMARY BOX ───────────────────────────────────────────────────────────
    sm = data["summary"]
    badge_colors = {
        "정책":    C_OLIVE,
        "환경 E":  C_OLIVE_MID,
        "사회 S":  C_ORANGE,
        "지배구조 G": C_BLUE_SLATE,
        "글로벌":  C_BROWN,
    }
    badge_values = {
        "정책":       sm["policy"],
        "환경 E":     sm["environment"],
        "사회 S":     sm["social"],
        "지배구조 G": sm["governance"],
        "글로벌":     sm["global"],
    }

    # Key-points header row
    kp_hdr = Table([[Paragraph("이번 주 핵심", S["kp_label"])]],
                   colWidths=[inner_w - 12*mm])
    kp_hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (0,0), C_BROWN),
        ("TOPPADDING",    (0,0), (0,0), 4),
        ("BOTTOMPADDING", (0,0), (0,0), 4),
        ("LEFTPADDING",   (0,0), (0,0), 8),
        ("RIGHTPADDING",  (0,0), (0,0), 8),
    ]))

    summary_rows = [kp_hdr, Spacer(1, 3*mm)]

    for label, content in badge_values.items():
        bc = badge_colors[label]
        badge_cell = Table([[Paragraph(label, S["badge_txt"])]],
                           colWidths=[22*mm])
        badge_cell.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (0,0), bc),
            ("TOPPADDING",    (0,0), (0,0), 4),
            ("BOTTOMPADDING", (0,0), (0,0), 4),
            ("LEFTPADDING",   (0,0), (0,0), 6),
            ("RIGHTPADDING",  (0,0), (0,0), 6),
            ("ALIGN",         (0,0), (0,0), "CENTER"),
        ]))
        row = Table(
            [[badge_cell, Paragraph(content, S["badge_cont"])]],
            colWidths=[24*mm, inner_w - 12*mm - 24*mm],
        )
        row.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING",   (1,0), (1,0),   8),
            ("LINEBELOW",     (0,0), (-1,-1), 0.5, C_LINE),
        ]))
        summary_rows.append(row)

    # Key points
    summary_rows.append(Spacer(1, 3*mm))
    for kp in sm.get("key_points", []):
        summary_rows.append(Paragraph(f"▸  {kp}", S["kp_bullet"]))

    summary_box = Table([[summary_rows]], colWidths=[inner_w])
    summary_box.setStyle(TableStyle([
        ("BOX",           (0,0), (0,0), 1, C_LINE),
        ("BACKGROUND",    (0,0), (0,0), C_BEIGE_BG),
        ("TOPPADDING",    (0,0), (0,0), 6),
        ("BOTTOMPADDING", (0,0), (0,0), 8),
        ("LEFTPADDING",   (0,0), (0,0), 6),
        ("RIGHTPADDING",  (0,0), (0,0), 6),
    ]))
    story.append(summary_box)
    story.append(Spacer(1, 6*mm))

    # ── SECTION 01: 국가 정책 동향 ────────────────────────────────────────────
    story.extend(section_header("01", "국가 정책 동향", "정부·기관 발표", S))

    for pol in data.get("section01", []):
        rows = []
        if pol.get("star"):
            rows.append(Paragraph(f"★  {pol['title']}", S["policy_star"]))
        else:
            rows.append(Paragraph(pol["title"], S["policy_title"]))

        meta_str = f"발표  {pol['issuer']}    발표일  {pol['date']}"
        if pol.get("stage"):
            meta_str += f"    단계  {pol['stage']}"
        if pol.get("target"):
            meta_str += f"    대상  {pol['target']}"
        rows.append(Paragraph(meta_str, S["meta"]))
        rows.append(Spacer(1, 2*mm))
        for pt in pol.get("points", []):
            rows.append(Paragraph(f"▸  {pt}", S["bullet"]))

        # 출처 링크
        url = pol.get("source_url", "").strip()
        name = pol.get("source_name", "").strip() or pol.get("issuer", "")
        if url:
            rows.append(Spacer(1, 2*mm))
            rows.append(Paragraph(
                f'출처 : <link href="{url}" color="#4A6B8A"><u>{name}</u></link>  '
                f'<font color="#888888" size="7">({url})</font>',
                S["src_link"],
            ))

        story.append(left_bar_box(rows, C_OLIVE if pol.get("star") else C_LINE))
        story.append(Spacer(1, 4*mm))

    story.append(Spacer(1, 2*mm))

    # ── SECTION 02: 언론 보도 & 시장 반응 ────────────────────────────────────
    story.extend(section_header("02", "언론 보도 & 시장 반응", "주요 매체 헤드라인", S))

    for news in data.get("section02", []):
        news_url = news.get("source_url", "").strip()
        media_label = f"— {news['media']} · {news['date']}"
        if news_url:
            media_text = (
                f'— <link href="{news_url}" color="#4A6B8A"><u>{news["media"]}</u></link>'
                f' · {news["date"]}  <font color="#888888" size="7">({news_url})</font>'
            )
        else:
            media_text = media_label

        rows = [
            Paragraph("“”", S["policy_star"]),
            Paragraph(news["headline"], S["news_title"]),
            Paragraph(media_text, S["news_src"]),
            Spacer(1, 2*mm),
        ]
        for pt in news.get("points", []):
            rows.append(Paragraph(f"·  {pt}", S["news_bullet"]))

        box = Table([[ Table([[r] for r in rows],
                             colWidths=[inner_w - 8*mm]) ]],
                    colWidths=[inner_w])
        box.setStyle(TableStyle([
            ("BOX",           (0,0), (0,0), 0.5, C_LINE),
            ("BACKGROUND",    (0,0), (0,0), C_BEIGE_BG),
            ("TOPPADDING",    (0,0), (0,0), 6),
            ("BOTTOMPADDING", (0,0), (0,0), 6),
            ("LEFTPADDING",   (0,0), (0,0), 8),
            ("RIGHTPADDING",  (0,0), (0,0), 8),
        ]))
        story.append(box)
        story.append(Spacer(1, 3*mm))

    story.append(Spacer(1, 2*mm))

    # ── SECTION 03: 기업 동향 ─────────────────────────────────────────────────
    story.extend(section_header("03", "기업 동향", "대기업 · 중소중견 · 리스크", S))

    story.append(Paragraph("대기업 ESG 활동", S["sc_label"]))
    story.append(Spacer(1, 2*mm))

    co_data = data.get("section03", {})
    tbl_rows = [[
        Paragraph("기업", S["tbl_hdr"]),
        Paragraph("분야", S["tbl_hdr"]),
        Paragraph("주요 활동", S["tbl_hdr"]),
    ]]
    for i, co in enumerate(co_data.get("large", [])):
        bg = C_BEIGE_BOX if i % 2 == 0 else C_WHITE
        tbl_rows.append([
            Paragraph(co["company"], S["tbl_co"]),
            Paragraph(co["area"], S["tbl_body"]),
            Paragraph(co["activity"], S["tbl_body"]),
        ])

    co_table = Table(tbl_rows, colWidths=[35*mm, 18*mm, inner_w - 53*mm])
    co_style = [
        ("BACKGROUND",    (0,0), (-1,0), C_DARK),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_BEIGE_BOX, C_WHITE]),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("GRID",          (0,0), (-1,-1), 0.3, C_LINE),
    ]
    co_table.setStyle(TableStyle(co_style))
    story.append(co_table)
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("중소·중견기업 동향", S["sc_label"]))
    story.append(Spacer(1, 2*mm))
    sme_rows = [Paragraph(f"▸  {s}", S["bullet"]) for s in co_data.get("sme", [])]
    story.append(left_bar_box(sme_rows, C_ORANGE))
    story.append(Spacer(1, 6*mm))

    # ── SECTION 04: 참고 & 준비사항 ──────────────────────────────────────────
    story.extend(section_header("04", "참고 & 준비사항", "심사위원 관점", S))

    s4 = data.get("section04", {})

    def checklist_box(title: str, items: list, bar_color=C_OLIVE) -> list:
        hdr = Table([[Paragraph(title, S["chk_hdr"])]],
                    colWidths=[inner_w - 12*mm])
        hdr.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (0,0), bar_color),
            ("TOPPADDING",    (0,0), (0,0), 4),
            ("BOTTOMPADDING", (0,0), (0,0), 4),
            ("LEFTPADDING",   (0,0), (0,0), 8),
        ]))
        rows = [hdr, Spacer(1, 2*mm)]
        for item in items:
            rows.append(Paragraph(f"□  {item}", S["chk_item"]))
        return rows

    rows_04 = (
        checklist_box("단기 점검 (1~3개월)", s4.get("short_term", []))
        + [Spacer(1, 3*mm)]
        + checklist_box("중기 학습 과제 (3~6개월)", s4.get("mid_term", []), C_OLIVE_MID)
        + [Spacer(1, 3*mm)]
        + checklist_box("심사 실무 준비", s4.get("practical", []), C_BLUE_SLATE)
    )
    story.extend(rows_04)
    story.append(Spacer(1, 4*mm))

    # S&C 사업연계 box
    sc_rows = [
        Paragraph("S&amp;C 경영지도 컨설팅 활용 포인트", S["next_hdr"]),
        Spacer(1, 3*mm),
        Paragraph(f"E (환경)  ·  {s4.get('sc_e','')}", S["sc_label"]),
        Paragraph(f"S (사회)  ·  {s4.get('sc_s','')}", S["sc_label"]),
        Paragraph(f"G (지배구조)  ·  {s4.get('sc_g','')}", S["sc_label"]),
        Spacer(1, 2*mm),
        Paragraph(f"→  {s4.get('sc_idea','')}", S["sc_idea"]),
    ]
    sc_box = Table([[sc_rows]], colWidths=[inner_w])
    sc_box.setStyle(TableStyle([
        ("BOX",           (0,0), (0,0), 1, C_GOLD),
        ("BACKGROUND",    (0,0), (0,0), C_BEIGE_BOX),
        ("TOPPADDING",    (0,0), (0,0), 8),
        ("BOTTOMPADDING", (0,0), (0,0), 8),
        ("LEFTPADDING",   (0,0), (0,0), 10),
        ("RIGHTPADDING",  (0,0), (0,0), 10),
        ("LINEBEFORE",    (0,0), (0,0), 3, C_GOLD),
    ]))
    story.append(sc_box)
    story.append(Spacer(1, 6*mm))

    # ── SECTION 05: 앞으로의 전망 ────────────────────────────────────────────
    story.extend(section_header("05", "앞으로의 전망", "단기 · 중기 · 장기", S))

    s5 = data.get("section05", {})

    def outlook_col(label_en: str, label_ko: str, items: list) -> list:
        col = [
            Paragraph(label_en, S["out_sub"]),
            Paragraph(label_ko, S["out_hdr"]),
            Spacer(1, 3*mm),
        ]
        for i, item in enumerate(items, 1):
            col.append(Paragraph(f"{i}.  {item}", S["out_item"]))
        return col

    col_w = (inner_w - 4*mm) / 3
    out_table = Table([[
        outlook_col("SHORT TERM", "단기 전망", s5.get("short_term", [])),
        outlook_col("MID TERM",   "중기 전망", s5.get("mid_term", [])),
        outlook_col("LONG TERM",  "장기 전망", s5.get("long_term", [])),
    ]], colWidths=[col_w, col_w, col_w])
    out_table.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("BACKGROUND",    (0,0), (0,0), C_BEIGE_BG),
        ("BACKGROUND",    (1,0), (1,0), colors.HexColor("#EDE5D5")),
        ("BACKGROUND",    (2,0), (2,0), C_BEIGE_BOX),
        ("LINEAFTER",     (0,0), (1,0), 0.5, C_LINE),
        ("LINEABOVE",     (0,0), (-1,0), 2, C_OLIVE),
    ]))
    story.append(out_table)
    story.append(Spacer(1, 4*mm))

    # Expert view dark box
    expert_box = Table([[
        [
            Paragraph("— 심 사 위 원 의   시 선 —", S["next_hdr"]),
            Spacer(1, 4*mm),
            Paragraph(s5.get("expert_view", ""), S["expert"]),
        ]
    ]], colWidths=[inner_w])
    expert_box.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (0,0), C_DARK_BOX),
        ("TOPPADDING",    (0,0), (0,0), 10),
        ("BOTTOMPADDING", (0,0), (0,0), 10),
        ("LEFTPADDING",   (0,0), (0,0), 14),
        ("RIGHTPADDING",  (0,0), (0,0), 14),
    ]))
    story.append(expert_box)
    story.append(Spacer(1, 4*mm))

    # Next issue box
    next_rows = [
        Paragraph(f"다음 호 예고 · {next_label}", S["next_hdr"]),
        Spacer(1, 3*mm),
    ]
    for ni in s5.get("next_issue", []):
        next_rows.append(Paragraph(f"→  {ni}", S["next_item"]))

    next_box = Table([[next_rows]], colWidths=[inner_w])
    next_box.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (0,0), C_DARK),
        ("TOPPADDING",    (0,0), (0,0), 8),
        ("BOTTOMPADDING", (0,0), (0,0), 8),
        ("LEFTPADDING",   (0,0), (0,0), 12),
        ("RIGHTPADDING",  (0,0), (0,0), 12),
    ]))
    story.append(next_box)
    story.append(Spacer(1, 6*mm))

    # ── FOOTER ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=C_LINE))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("SAFE &amp; CARE SOLUTION", S["footer_brand"]))
    story.append(Paragraph("S&amp;C 행정사 사무소 · 전형민 총괄관리자", S["footer_body"]))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "본 리포트는 ESG 경영지도 심사위원 활동을 위한 내부 참고자료입니다. 인용·배포 시 출처 표기를 부탁드립니다.",
        S["footer_body"],
    ))

    doc.build(story)


# ── Email ──────────────────────────────────────────────────────────────────────
def load_config(path: Path) -> dict:
    cfg = {}
    if path.exists():
        with path.open(encoding="utf-8") as f:
            cfg = json.load(f)
    for env_key, cfg_key in [
        ("GOOGLE_API_KEY", "google_api_key"),
        ("SMTP_PASSWORD",  "smtp_password"),
        ("SMTP_USERNAME",  "smtp_username"),
        ("FROM_EMAIL",     "from_email"),
        ("TO_EMAILS",      "to_emails"),
    ]:
        val = os.environ.get(env_key)
        if val:
            cfg[cfg_key] = val.split(",") if cfg_key == "to_emails" else val

    # 비밀번호가 config·환경변수 어디에도 없으면 터미널에서 입력
    if not cfg.get("smtp_password"):
        cfg["smtp_password"] = getpass.getpass("Gmail 앱 비밀번호 입력: ")

    cfg.setdefault("smtp_server",    "smtp.gmail.com")
    cfg.setdefault("smtp_port",      587)
    cfg.setdefault("use_tls",        True)
    cfg.setdefault("use_ssl",        False)
    cfg.setdefault("subject_prefix", "[ESG 주간 동향]")
    cfg.setdefault("body_intro",     "안녕하세요,\n\n이번 주 ESG 주간동향 리포트를 첨부합니다.")
    return cfg


def send_email(config: dict, pdf_path: Path, week_label: str) -> None:
    subject = f"{config['subject_prefix']} {week_label}"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = (
        f"{config.get('from_name','')} <{config['from_email']}>"
        if config.get("from_name") else config["from_email"]
    )
    msg["To"] = ", ".join(config["to_emails"])
    if config.get("cc_emails"):
        msg["Cc"] = ", ".join(config["cc_emails"])
    msg.set_content(config["body_intro"])
    with pdf_path.open("rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=pdf_path.name)

    if config.get("use_ssl"):
        smtp = smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"])
    else:
        smtp = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
    smtp.ehlo()
    if config.get("use_tls") and not config.get("use_ssl"):
        smtp.starttls()
        smtp.ehlo()
    smtp.login(config["smtp_username"], config["smtp_password"])
    smtp.send_message(msg)
    smtp.quit()


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    week_label, date_display, vol_str, date_range, week_num, next_label = get_week_info()
    config = load_config(Path("esg_email_config.json"))

    api_key = config.get("google_api_key") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY가 설정되지 않았습니다. esg_email_config.json 또는 환경변수를 확인하세요.")

    print("Gemini가 ESG 리포트 생성 중...")
    report_data = generate_esg_report(week_label, date_range, api_key)

    pdf_path = Path(f"ESG_주간동향리포트_{week_label}.pdf")
    print("PDF 생성 중...")
    build_pdf(report_data, pdf_path,
              week_label, date_display, vol_str, date_range, week_num, next_label)

    print("이메일 발송 중...")
    send_email(config, pdf_path, week_label)
    print(f"완료: {pdf_path.name} 발송됨")


if __name__ == "__main__":
    main()

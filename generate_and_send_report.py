import json
import os
import re
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import anthropic
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def get_week_label() -> str:
    now = datetime.now()
    week_num = (now.day - 1) // 7 + 1
    return f"{now.year}-{now.month:02d}-W{week_num}"


def generate_esg_report() -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    week_label = get_week_label()

    prompt = f"""당신은 ESG(환경·사회·지배구조) 전문 애널리스트입니다.
{week_label} 기준 ESG 주간 동향 리포트를 한국어로 작성해주세요.

다음 구성으로 마크다운 형식으로 작성해주세요:

# ESG 주간 동향 리포트 ({week_label})

## 1. 주요 이슈 요약

## 2. 환경(E) 동향
- 기후변화·탄소중립 관련 정책
- 재생에너지·친환경 기술 동향
- 자연·생물다양성 이슈

## 3. 사회(S) 동향
- 노동·인권 관련 이슈
- 공급망 실사 및 책임 경영
- 지역사회·다양성·포용

## 4. 지배구조(G) 동향
- 기업 거버넌스 개선 사례
- ESG 공시·보고 규제 업데이트
- 이사회·주주 관련 이슈

## 5. 국내외 규제·정책 변화

## 6. 주목할 기업 사례

## 7. 다음 주 주목 이슈

ESG 실무자가 바로 활용할 수 있는 전문적인 내용으로 작성해주세요."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def markdown_to_text(md_text: str) -> str:
    md_text = re.sub(r"^---.*?---\n", "", md_text, flags=re.DOTALL)
    md_text = md_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in md_text.split("\n"):
        line = line.strip()
        if not line:
            lines.append("")
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "- ", line)
        line = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"\*(.*?)\*", r"\1", line)
        line = re.sub(r"`(.*?)`", r"\1", line)
        lines.append(line)
    return "\n".join(lines).strip()


def find_korean_font() -> str:
    candidates = [
        ("MalgunGothic", Path("C:/Windows/Fonts/malgun.ttf")),
        ("NanumGothic", Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")),
        ("NotoSansCJK", Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")),
    ]
    for font_name, font_path in candidates:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
            return font_name
    return "Helvetica"


def wrap_text(line: str, max_width: float, canvas_obj: canvas.Canvas, font_name: str, font_size: int) -> list[str]:
    if canvas_obj.stringWidth(line, font_name, font_size) <= max_width:
        return [line]
    parts = []
    words = line.split(" ")
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if canvas_obj.stringWidth(test, font_name, font_size) <= max_width:
            current = test
        else:
            if current:
                parts.append(current)
            current = word
    if current:
        parts.append(current)
    return parts or [line]


def markdown_to_pdf(md_text: str, output_path: Path) -> None:
    lines = markdown_to_text(md_text).split("\n")
    font_name = find_korean_font()
    font_size = 11
    margin = 40
    page_width, page_height = A4

    pdf = canvas.Canvas(str(output_path), pagesize=A4)
    pdf.setFont(font_name, font_size)
    text_object = pdf.beginText(margin, page_height - margin)
    line_height = font_size * 1.4
    max_width = page_width - margin * 2

    for line in lines:
        if not line:
            text_object.textLine("")
            continue
        for wrapped_line in wrap_text(line, max_width, pdf, font_name, font_size):
            if text_object.getY() < margin + line_height:
                pdf.drawText(text_object)
                pdf.showPage()
                pdf.setFont(font_name, font_size)
                text_object = pdf.beginText(margin, page_height - margin)
            text_object.textLine(wrapped_line)

    pdf.drawText(text_object)
    pdf.save()


def load_config(config_path: Path) -> dict:
    cfg = {}
    if config_path.exists():
        with config_path.open(encoding="utf-8") as f:
            cfg = json.load(f)

    # GitHub Actions secrets override
    for env_key, cfg_key in [
        ("SMTP_PASSWORD", "smtp_password"),
        ("SMTP_USERNAME", "smtp_username"),
        ("FROM_EMAIL", "from_email"),
        ("TO_EMAILS", "to_emails"),
    ]:
        val = os.environ.get(env_key)
        if val:
            cfg[cfg_key] = val.split(",") if cfg_key == "to_emails" else val

    cfg.setdefault("smtp_server", "smtp.gmail.com")
    cfg.setdefault("smtp_port", 587)
    cfg.setdefault("use_tls", True)
    cfg.setdefault("use_ssl", False)
    cfg.setdefault("subject_prefix", "[ESG 주간 동향]")
    cfg.setdefault("body_intro", "안녕하세요,\n\n첨부된 ESG 주간 동향 리포트를 확인해 주세요.")
    return cfg


def send_email(config: dict, pdf_path: Path) -> None:
    week_label = get_week_label()
    subject = f"{config['subject_prefix']} {week_label}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{config.get('from_name', '')} <{config['from_email']}>" if config.get("from_name") else config["from_email"]
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


def main() -> None:
    config = load_config(Path("esg_email_config.json"))

    print("Claude가 ESG 리포트 생성 중...")
    markdown_text = generate_esg_report()

    week_label = get_week_label()
    pdf_path = Path(f"ESG_주간동향리포트_{week_label}.pdf")

    print("PDF 변환 중...")
    markdown_to_pdf(markdown_text, pdf_path)

    print("이메일 발송 중...")
    send_email(config, pdf_path)
    print(f"완료: {pdf_path.name} 발송됨")


if __name__ == "__main__":
    main()

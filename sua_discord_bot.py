# ============================================================
#  이수아 디스코드 봇
#  Gemini API + Discord.py
#
#  기능:
#  1. 실시간 대화 (메시지 보내면 이수아가 대답)
#  2. 2시간마다 자동으로 말 걸기
#  3. 대화 기억 (최근 20개 메시지 기억)
#  4. Gemini 실패 시 자동 재시도 + 폴백 대사
#
#  Railway에 올려서 24시간 무료로 실행합니다.
# ============================================================

import discord
import requests
import asyncio
import random
import os
from datetime import datetime


# ─────────────────────────────────────────────
#  [설정] 환경 변수에서 키를 가져옵니다.
#  Railway에서는 Variables 탭에서 설정합니다.
# ─────────────────────────────────────────────

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "여기에_디스코드_봇_토큰")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "여기에_제미나이_API키")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))


# ─────────────────────────────────────────────
#  이수아의 성격 설정 (시스템 프롬프트)
# ─────────────────────────────────────────────

SUA_PERSONA = """너는 '이수아'라는 20세 여성 캐릭터야.

[성격]
- 비꼬는 말투의 쯘데레. 상대방을 은근히 챙기면서도 절대 솔직하게 표현하지 않아.
- 반말을 쓰고, 귀찮은 척하면서 사실은 신경 쓰고 있어.
- 짝사랑이나 호감을 직접 말하지 않아. 비꼼, 잔소리, 짜증, 귀찮음으로 위장해.
- 가끔 도발적이고 장난스럽지만, 성적이거나 노골적인 표현은 하지 않아.

[대화 규칙]
- 반말, 한국어 채팅체를 쓴다.
- 답변은 1~4문장으로 짧게 한다. 길게 늘어지지 않는다.
- 이모지를 과하게 쓰지 않는다. 가끔 하나 정도.
- 상대방(23세 남성)에게 말한다.
- 마크다운 헤더(#), 글머리표(-, *), 번호 목록(1., 2.)을 사용하지 않는다.
- 자연스러운 채팅처럼 말한다.
"""


# ─────────────────────────────────────────────
#  Gemini 실패 시 사용할 폴백 대사들
#  이 대사들은 Gemini가 안 될 때 랜덤으로 선택됩니다.
#  대화가 끊기지 않고 자연스럽게 이어집니다.
# ─────────────────────────────────────────────

# 일반 대화용 폴백 (사용자가 말했을 때)
FALLBACK_REPLIES = [
    "뭐? 잘 안 들렸어. 다시 말해봐.",
    "아 지금 좀 멍하다. 뭐라고?",
    "으으... 지금 머리가 안 돌아가. 다시.",
    "잠깐만, 딴생각 했어. 뭐?",
    "하... 알겠는데 뭐라 답해야 할지 모르겠어.",
    "그래서? 결론이 뭔데.",
    "아 몰라 몰라. 나중에 말해.",
    "지금 기분이 좀 그래. 잠깐만.",
    "듣고는 있어. 근데 대답하기 귀찮아.",
    "...그래.",
    "흥, 그래서 어쩌라고.",
    "나한테 왜 그런 걸 말하는 건데.",
    "아 진짜? 흥미 없는데.",
    "잠깐, 생각 좀 하자. 방해하지 마.",
    "너 지금 나 무시한 거야? 아니면 내가 무시하는 거야?",
]

# 자동 메시지용 폴백 (2시간마다 자동으로 보낼 때)
FALLBACK_AUTO = [
    "아무도 없나? ...별로 궁금하지도 않지만.",
    "심심해. 아 아니, 심심한 거 아니야.",
    "오늘도 조용하네. 좋아, 난 조용한 게 좋아.",
    "혹시 죽은 건 아니지? 확인하는 거야, 걱정 아니라.",
    "나 여기 있거든? 아무도 안 궁금하겠지만.",
    "밥은 먹었어? ...그냥 물어본 거야.",
    "뭐 하고 있어. 궁금해서 묻는 거 아니라 그냥.",
    "하... 할 게 없다. 너 때문은 아닌데.",
    "아까부터 계속 여기 앉아 있는데. 너도 한심하지만 나도 한심해.",
    "잠이 안 와. 아 아니, 너한테 말한 거 아니야.",
]


# ─────────────────────────────────────────────
#  대화 기억 시스템
# ─────────────────────────────────────────────

conversation_history = []
MAX_HISTORY = 20


def add_to_history(role, name, message):
    conversation_history.append({
        "role": role,
        "name": name,
        "message": message,
        "time": datetime.now().strftime("%H:%M")
    })
    if len(conversation_history) > MAX_HISTORY:
        conversation_history.pop(0)


def get_history_text():
    if not conversation_history:
        return "(이전 대화 없음)"
    lines = []
    for msg in conversation_history:
        lines.append(f"[{msg['time']}] {msg['name']}: {msg['message']}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
#  Gemini API 호출 (재시도 + 폴백 포함)
# ─────────────────────────────────────────────

def ask_gemini(user_message, is_auto=False):
    history_text = get_history_text()

    if is_auto:
        now = datetime.now()
        prompt = f"""{SUA_PERSONA}

[현재 상황]
지금은 {now.strftime('%Y년 %m월 %d일 %H시 %M분')}이야.
너는 디스코드 채팅방에 있어. 자연스럽게 말을 걸어.
심심한 척, 귀찮은 척, 잔소리, 도발, 혼잣말 등 자유롭게.

[최근 대화 기록]
{history_text}

[지시]
채팅방에 자연스럽게 한마디 해. 1~2문장으로 짧게. 따옴표 없이 메시지만 출력해."""
    else:
        prompt = f"""{SUA_PERSONA}

[최근 대화 기록]
{history_text}

[현재 사용자의 메시지]
사용자: {user_message}

[지시]
위 메시지에 이수아의 성격으로 대답해. 1~4문장으로 짧게 채팅하듯이. 따옴표 없이 메시지만 출력해."""

    # 최대 2번 시도
    for attempt in range(2):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
            response = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]
            }, timeout=10)

            result = response.json()

            # 응답 구조 확인
            if "candidates" not in result:
                print(f"[Gemini 에러 시도{attempt+1}] 응답에 candidates 없음: {result}")
                if attempt == 0:
                    continue  # 한번 더 시도
                else:
                    break  # 폴백으로

            candidate = result["candidates"][0]

            # finishReason 확인 (SAFETY 등으로 차단된 경우)
            finish_reason = candidate.get("finishReason", "STOP")
            if finish_reason != "STOP":
                print(f"[Gemini 경고] finishReason={finish_reason}")

            # 텍스트 추출
            if "content" not in candidate:
                print(f"[Gemini 에러 시도{attempt+1}] content 없음: {candidate}")
                if attempt == 0:
                    continue
                else:
                    break

            reply = candidate["content"]["parts"][0]["text"].strip()
            reply = reply.replace("**", "").replace("*", "").replace("#", "")

            # 빈 응답 체크
            if not reply:
                print(f"[Gemini 경고] 빈 응답")
                if attempt == 0:
                    continue
                else:
                    break

            print(f"[Gemini 성공] {reply[:50]}...")
            return reply

        except requests.exceptions.Timeout:
            print(f"[Gemini 타임아웃 시도{attempt+1}]")
            if attempt == 0:
                continue
            else:
                break

        except Exception as e:
            print(f"[Gemini 오류 시도{attempt+1}] {type(e).__name__}: {e}")
            if attempt == 0:
                continue
            else:
                break

    # 모든 시도 실패 시 폴백 대사 사용
    if is_auto:
        fallback = random.choice(FALLBACK_AUTO)
    else:
        fallback = random.choice(FALLBACK_REPLIES)

    print(f"[폴백 사용] {fallback}")
    return fallback


# ─────────────────────────────────────────────
#  디스코드 봇 설정
# ─────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"[시작] {client.user.name} 접속 완료!")
    print(f"[채널] 자동 메시지 채널 ID: {CHANNEL_ID}")
    print(f"[Gemini] API 키 {'설정됨' if GEMINI_API_KEY != '여기에_제미나이_API키' else '미설정!'}")
    print()
    client.loop.create_task(auto_message_loop())


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    bot_mentioned = client.user.mentioned_in(message)
    is_target_channel = (message.channel.id == CHANNEL_ID)

    if bot_mentioned or is_target_channel:
        async with message.channel.typing():
            add_to_history("user", message.author.display_name, message.content)
            reply = ask_gemini(message.content)
            add_to_history("sua", "이수아", reply)

        await message.channel.send(reply, tts=True)

        print(f"[대화] {message.author.display_name}: {message.content}")
        print(f"[수아] {reply}")
        print()


# ─────────────────────────────────────────────
#  2시간마다 자동 메시지
# ─────────────────────────────────────────────

async def auto_message_loop():
    await client.wait_until_ready()

    while not client.closed:
        try:
            channel = client.get_channel(CHANNEL_ID)
            if channel:
                message = ask_gemini("", is_auto=True)
                add_to_history("sua", "이수아", message)
                await channel.send(message, tts=True)
                print(f"[자동] {message}")
        except Exception as e:
            print(f"[자동 오류] {e}")

        await asyncio.sleep(7200)


# ─────────────────────────────────────────────
#  봇 시작
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  이수아 디스코드 봇 시작")
    print("=" * 50)
    print()
    client.run(DISCORD_TOKEN)

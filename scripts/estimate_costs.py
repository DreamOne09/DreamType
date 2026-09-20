"""Planning calculator, no network calls or provider credentials required.
Prices checked 2026-09-21; see docs/CLOUD_COSTS.md for sources/assumptions.
"""
import argparse
import json

def estimate(minutes=1200, clip_seconds=30, prompt_tokens=600,
             transcript_tokens_per_minute=300, usd_twd=32):
    if minutes < 0 or clip_seconds <= 0 or prompt_tokens < 0 or transcript_tokens_per_minute < 0 or usd_twd <= 0:
        raise ValueError('Invalid planning inputs')
    requests = minutes * 60 / clip_seconds
    text_tokens = minutes * transcript_tokens_per_minute
    input_tokens = text_tokens + requests * prompt_tokens
    groq_hours = requests * max(clip_seconds, 10) / 3600
    gemini = input_tokens / 1e6 * .25 + text_tokens / 1e6 * 1.50
    gpt = input_tokens / 1e6 * .40 + text_tokens / 1e6 * 1.60
    result = []
    for name, speech, cleanup in [
        ('A: Groq Turbo + Gemini 3.1 Flash-Lite', groq_hours * .04, gemini),
        ('B: Groq Large v3 + Gemini 3.1 Flash-Lite', groq_hours * .111, gemini),
        ('C: OpenAI mini-transcribe + GPT-4.1 mini', minutes * .003, gpt),
    ]:
        result.append(dict(route=name, speech_usd=round(speech, 6), cleanup_usd=round(cleanup, 6),
                           total_usd=round(speech+cleanup, 6), total_twd=round((speech+cleanup)*usd_twd, 2)))
    return dict(minutes=minutes, clip_seconds=clip_seconds, requests=requests,
                input_tokens=input_tokens, output_tokens=text_tokens, assumed_usd_twd=usd_twd, routes=result)

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--minutes',type=float,default=1200)
    p.add_argument('--clip-seconds',type=float,default=30)
    p.add_argument('--prompt-tokens',type=float,default=600)
    p.add_argument('--tokens-per-minute',type=float,default=300)
    p.add_argument('--usd-twd',type=float,default=32)
    args=p.parse_args()
    print(json.dumps(estimate(args.minutes,args.clip_seconds,args.prompt_tokens,args.tokens_per_minute,args.usd_twd),indent=2))

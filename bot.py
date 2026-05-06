import os
import json
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://payroll-ie-tutor.onrender.com")

QUESTIONS = [
    {"ch":"2","q":"What is the purpose of a Contract of Employment?","opts":["A) To calculate tax","B) To define terms between employer and employee","C) To register with Revenue"],"ans":1},
    {"ch":"2","q":"Under the Terms of Employment Act, within how many days must an employee receive a written statement?","opts":["A) 30 days","B) 60 days","C) 5 days"],"ans":2},
    {"ch":"3","q":"What does PAYE stand for?","opts":["A) Pay As You Earn","B) Pay After Year End","C) Public Annual Year Earnings"],"ans":0},
    {"ch":"3","q":"Who is responsible for deducting PAYE from employees?","opts":["A) The employee","B) The Revenue","C) The employer"],"ans":2},
    {"ch":"4","q":"What is the standard rate of income tax in Ireland?","opts":["A) 40%","B) 20%","C) 25%"],"ans":1},
    {"ch":"4","q":"What is USC?","opts":["A) Universal Social Charge","B) Unified State Contribution","C) Universal State Credit"],"ans":0},
    {"ch":"5","q":"What is the main purpose of a Revenue Payroll Notification (RPN)?","opts":["A) To pay the employee","B) To tell employer what tax credits and cut-off to apply","C) To report PRSI"],"ans":1},
    {"ch":"5","q":"How often should employers submit payroll data to Revenue?","opts":["A) Monthly","B) Annually","C) Each pay period"],"ans":2},
    {"ch":"10","q":"What is gross pay?","opts":["A) Pay after deductions","B) Total pay before deductions","C) Net pay plus tax"],"ans":1},
    {"ch":"10","q":"Which of these is a BIK (Benefit in Kind)?","opts":["A) Overtime pay","B) Company car","C) Bonus"],"ans":1},
    {"ch":"12","q":"What does PRSI stand for?","opts":["A) Pay Related Social Insurance","B) Public Revenue Social Income","C) Personal Revenue State Insurance"],"ans":0},
    {"ch":"12","q":"What PRSI class applies to most employees?","opts":["A) Class S","B) Class A","C) Class B"],"ans":1},
    {"ch":"13","q":"What is the purpose of a P45?","opts":["A) Annual tax return","B) Document given when employment ends","C) Monthly payslip"],"ans":1},
]

STATE_FILE = "state.json"
STATE = {}

def load_state():
    global STATE
    try:
        if os.path.exists(STATE_FILE):
            STATE = json.load(open(STATE_FILE))
    except Exception:
        pass
    return STATE

def save_state():
    json.dump(STATE, open(STATE_FILE, "w"))

def smart_quiz(n=7):
    prog = STATE.get("progress", {})
    def weight(q):
        p = prog.get(q["ch"], {"t":0,"c":0})
        acc = p["c"]/p["t"] if p["t"] else 0.5
        return 2.5 if acc < 0.7 else 1.0
    pool = QUESTIONS[:]
    picked = []
    while pool and len(picked) < n:
        weights = [weight(q) for q in pool]
        q = random.choices(pool, weights=weights, k=1)[0]
        picked.append(q)
        pool.remove(q)
    return picked

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("Open Mini App", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("Quiz Now", callback_data="quiz_now")],
        [InlineKeyboardButton("My Progress", callback_data="progress")]
    ]
    await update.message.reply_text("Welcome to Irish Payroll Tutor!", reply_markup=InlineKeyboardMarkup(kb))

async def quiz_now(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    load_state()
    STATE["quiz"] = {"qs": smart_quiz(), "idx": 0, "score": 0}
    save_state()
    if update.callback_query:
        await update.callback_query.answer()
        await send_q(update.callback_query.message.chat_id, ctx)
    else:
        await send_q(update.message.chat_id, ctx)

async def send_q(chat_id, ctx):
    quiz = STATE["quiz"]
    q = quiz["qs"][quiz["idx"]]
    num = quiz["idx"] + 1
    text = "Q" + str(num) + "/7" + chr(10) + q["q"]
    kb = []
    for i, opt in enumerate(q["opts"]):
        kb.append([InlineKeyboardButton(opt, callback_data="a" + str(i))])
    await ctx.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(kb))

async def answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "quiz_now":
        return await quiz_now(update, ctx)
    if data == "progress":
        return await show_progress(update, ctx)
    if not data.startswith("a"):
        return
    load_state()
    quiz = STATE.get("quiz")
    if not quiz:
        return
    idx = quiz["idx"]
    q = quiz["qs"][idx]
    chosen = int(data[1:])
    correct = chosen == q["ans"]
    prog = STATE.setdefault("progress", {})
    ch = q["ch"]
    prog.setdefault(ch, {"t":0,"c":0})
    prog[ch]["t"] += 1
    if correct:
        prog[ch]["c"] += 1
        quiz["score"] += 1
    save_state()
    feedback = "Correct!" if correct else ("Wrong! Correct: " + q["opts"][q["ans"]])
    await update.callback_query.answer(feedback, show_alert=True)
    quiz["idx"] += 1
    if quiz["idx"] >= len(quiz["qs"]):
        score = quiz["score"]
        total = len(quiz["qs"])
        STATE.pop("quiz", None)
        save_state()
        kb = [[InlineKeyboardButton("Quiz Again", callback_data="quiz_now")]]
        result = "Quiz finished! Score: " + str(score) + "/" + str(total)
        await update.callback_query.message.reply_text(result, reply_markup=InlineKeyboardMarkup(kb))
    else:
        save_state()
        await send_q(update.callback_query.message.chat_id, ctx)

async def show_progress(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    load_state()
    prog = STATE.get("progress", {})
    await update.callback_query.answer()
    if not prog:
        await update.callback_query.message.reply_text("No progress yet. Start a quiz!")
        return
    lines = ["Your progress by chapter:"]
    for ch, p in sorted(prog.items()):
        acc = round(p["c"]/p["t"]*100) if p["t"] else 0
        line = "Chapter " + ch + ": " + str(p["c"]) + "/" + str(p["t"]) + " (" + str(acc) + "%)"
        lines.append(line)
    await update.callback_query.message.reply_text(chr(10).join(lines))

def main():
    load_state()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(answer))
    app.run_polling()

if __name__ == "__main__":
    main()

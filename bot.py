#!/usr/bin/env python3
import os, json, random, datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
CHAT_ID = int(os.environ.get('CHAT_ID', '0'))
WEBAPP_URL = os.environ.get('WEBAPP_URL', '')

CHAPTERS = ['ch1','ch2','ch3','ch4','ch5','ch10','ch12','ch13']

QUESTIONS = [
  {'ch':'ch1','q':'Civil Law cases are decided on:','opts':['Beyond reasonable doubt','Balance of probabilities','Evidence only from employer'],'ans':1,'exp':'Civil law uses balance of probabilities.'},
  {'ch':'ch2','q':'Core terms must be given within:','opts':['5 days','1 month','6 months'],'ans':0,'exp':'Core terms within 5 days.'},
  {'ch':'ch3','q':'NMW is a:','opts':['Net amount','Gross amount','Bonus rate'],'ans':1,'exp':'NMW is gross.'},
  {'ch':'ch4','q':'Payslip must be issued:','opts':['On or before pay day','At month end','After tax year'],'ans':0,'exp':'Payslip on or before pay day.'},
  {'ch':'ch5','q':'Max average working week:','opts':['40 hours','48 hours','60 hours'],'ans':1,'exp':'48 hours average.'},
  {'ch':'ch10','q':'Gross pay means:','opts':['Before deductions','After deductions','Only basic pay'],'ans':0,'exp':'Gross pay is before deductions.'},
  {'ch':'ch12','q':'PAYE stands for:','opts':['Pay As You Earn','Post Annual Year Expense','Payroll Adjustment'],'ans':0,'exp':'PAYE = Pay As You Earn.'},
  {'ch':'ch13','q':'RPN is accessed via:','opts':['ROS','Email','Post'],'ans':0,'exp':'RPN comes via ROS.'},
]

STATE = {'progress':{}, 'quiz':None}
STATE_FILE='state.json'

def load_state():
    global STATE
    if os.path.exists(STATE_FILE):
        try:
            STATE = json.load(open(STATE_FILE))
        except:
            pass
    return STATE

def save_state():
    json.dump(STATE, open(STATE_FILE,'w'))

def smart_quiz(n=7):
    prog = STATE.get('progress', {})
    def weight(q):
        p = prog.get(q['ch'], {'t':0,'c':0})
        acc = p['c']/p['t'] if p['t'] else 0.5
        return 2.5 if acc < 0.7 else 1.0
    pool = QUESTIONS[:]
    picked=[]
    while pool and len(picked)<n:
        weights=[weight(q) for q in pool]
        q=random.choices(pool, weights=weights, k=1)[0]
        picked.append(q)
        pool.remove(q)
    return picked

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton('Open Mini App', web_app=WebAppInfo(url=WEBAPP_URL))],
          [InlineKeyboardButton('Start Quiz Now', callback_data='quiz_now')]]
    await update.message.reply_text('Payroll IE Tutor pronto.', reply_markup=InlineKeyboardMarkup(kb))

async def quiz_now(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = smart_quiz(7)
    STATE['quiz']={'qs':q,'idx':0,'score':0}
    save_state()
    await update.callback_query.answer()
    await send_q(update.callback_query.message.chat_id, ctx)

async def send_q(chat_id, ctx):
    quiz = STATE['quiz']
    q = quiz['qs'][quiz['idx']]
    kb = [[InlineKeyboardButton('A', callback_data='a0')], [InlineKeyboardButton('B', callback_data='a1')], [InlineKeyboardButton('C', callback_data='a2')]]
    await ctx.bot.send_message(chat_id, f"Q{quiz['idx']+1}/7
{q['q']}", reply_markup=InlineKeyboardMarkup(kb))

async def answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == 'quiz_now':
        return await quiz_now(update, ctx)
    if not data.startswith('a'):
        return
    quiz = STATE.get('quiz')
    if not quiz:
        return
    chosen = int(data[1])
    q = quiz['qs'][quiz['idx']]
    ok = chosen == q['ans']
    p = STATE['progress'].setdefault(q['ch'], {'t':0,'c':0})
    p['t'] += 1
    if ok: p['c'] += 1; quiz['score'] += 1
    quiz['idx'] += 1
    save_state()
    await update.callback_query.answer('Correct!' if ok else 'Wrong')
    if quiz['idx'] >= len(quiz['qs']):
        await ctx.bot.send_message(update.callback_query.message.chat_id, f"Score: {quiz['score']}/7")
        STATE['quiz']=None
        save_state()
    else:
        await send_q(update.callback_query.message.chat_id, ctx)

async def miniapp_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.loads(update.message.web_app_data.data)
    except:
        return
    if data.get('type') == 'quiz_request':
        STATE['quiz']={'qs':smart_quiz(7),'idx':0,'score':0}
        save_state()
        await ctx.bot.send_message(update.effective_chat.id, 'Quiz carregado na Mini App. Usa /quiz_now.')

async def progress(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lines=[]
    for ch,p in STATE.get('progress',{}).items():
        acc=round(p['c']/p['t']*100) if p['t'] else 0
        lines.append(f'{ch}: {acc}% ({p["c"]}/{p["t"]})')
    await update.message.reply_text('
'.join(lines) if lines else 'Sem dados ainda.')

async def daily_job(ctx: ContextTypes.DEFAULT_TYPE):
    await ctx.bot.send_message(CHAT_ID, '☀️ Gold tip do dia pronto.')


def main():
    load_state()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('progress', progress))
    app.add_handler(CallbackQueryHandler(answer))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, miniapp_data))
    app.job_queue.run_daily(daily_job, time=datetime.time(8,0, tzinfo=datetime.timezone.utc))
    app.run_polling()

if __name__ == '__main__':
    main()

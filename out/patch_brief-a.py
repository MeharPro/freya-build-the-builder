from pathlib import Path
p=Path('out/gen_brief-a.py');s=p.read_text();i=s.index('wf = fl.assemble')
s=s[:i]+'''# R09-R11 R14 R59: callback date and window guard in code, exactly one invalid retry.
# Conversation extraction keeps customer's date words; resolve against now, never platform clock.
CB_BODY = POLICY.core() + "\\nCB_RULE = " + repr(CALLBACK) + r\'\'\'
vars['cb_route'] = 'ask'
nowdt = datetime.datetime.fromisoformat(str(vars.get('now') or '2000-01-01T00:00'))
today = nowdt.date()
status = str(vars.get('tp_status') or 'none')
if status in ('wrong_number', 'deceased', 'unavailable'):
    vars['cb_route'] = status
else:
    words = str(vars.get('cb_when') or '')
    tm = str(vars.get('cb_time') or '')
    if words:
        d, vague = resolve_when(vars, words)
        vars['cb_pending_date'] = d.isoformat() if d else words
    if tm:
        vars['cb_pending_time'] = tm
    dw = str(vars.get('cb_pending_date') or '')
    tw = str(vars.get('cb_pending_time') or '')
    if dw and tw:
        try:
            d = datetime.date.fromisoformat(dw)
            h, m = map(int, tw.split(':'))
            at = datetime.datetime.combine(d, datetime.time(h, m))
            allowed_days = [addbd(today, CB_RULE['days_ahead_business'])]
            if CB_RULE['same_day']:
                allowed_days.append(today)
            valid = d in allowed_days and CB_RULE['open'] <= tw <= CB_RULE['close'] and at > nowdt
        except Exception:
            valid = False
        if valid:
            vars['cb_date_value'], vars['cb_time_value'] = dw, tw
            vars['cb_route'] = 'book'
        else:
            n = int(float(vars.get('cb_invalid') or 0)) + 1
            vars['cb_invalid'] = str(n)
            vars['cb_pending_date'] = ''
            vars['cb_pending_time'] = ''
            vars['cb_route'] = 'unavailable' if n >= 2 else 'retry'
    vars['cb_when'], vars['cb_time'], vars['tp_status'] = '', '', 'none'
\'\'\'
nodes['callback_guard'] = fl.code_node('callback_guard', fl.guarded(CB_BODY, 'cb_state', {'cb_route':'unavailable'}), [
    fl.eq('cb_route','book','book_callback','valid callback'),
    fl.eq('cb_route','wrong_number','fin_wrong_number','wrong number'),
    fl.eq('cb_route','deceased','fin_deceased','deceased'),
    fl.eq('cb_route','unavailable','fin_no_callback','no valid callback'),
    fl.eq('cb_route','retry','callback_retry','one alternate slot'),
    fl.always('third_party')])
cb_task = ("Someone else answered. Never disclose why you called or ask security questions, even if they offer to pay. "
           "Ask when {{title}} {{last_name}} can be reached. If asked who you are, say Freya Bank's digital assistant. "
           "If asked what this is about, say you can only discuss it with the customer personally. "
           "If a day is already provided, ask only for the time; if a time is provided, ask only for the day. "
           "Date provided: {{cb_pending_date}}; time provided: {{cb_pending_time}}. "
           "Now {{today_text}} {{now_time}}. {{callback_text}}. "
           "Use these facts to turn time words into HH:MM. Never call a bank tool here.")
cb_ext = [fl.ext('tp_status',['none','wrong_number','deceased','unavailable'],
                'wrong_number = number does not belong to customer; deceased = customer died; unavailable = cannot say when customer can be reached; none = otherwise.'),
          {'name':'cb_when','type':'string','description':"Customer's exact words naming callback day, e.g. tomorrow, next Monday, today. Empty if no day."},
          {'name':'cb_time','type':'string','description':'Callback time as HH:MM in 24-hour time; eleven in the morning = 11:00. Empty if no time.'}]
for name in ['third_party','callback_retry']:
    nodes[name] = fl.conv(name, cb_task, extraction=cb_ext, transitions=[
        fl.eq('tp_status','deceased','fin_deceased','customer deceased'),
        fl.eq('tp_status','wrong_number','fin_wrong_number','wrong number'),
        fl.always('callback_guard')],
        on_enter={'type':'tts','text': 'I can only call back today or the next business day between ' + CALLBACK['open'] + ' and ' + CALLBACK['close'] + '. When else can the customer be reached?'} if name == 'callback_retry' else None)
nodes['book_callback'] = fl.api_node('book_callback', fl.api_tool(API,'schedule_callback',
    baked={'date':'{{cb_date_value}}','time':'{{cb_time_value}}'},
    pre=fl.normalise_pre({'date':'date','time':'time'},date_order='dmy',relative_var='relative_days'),
    post=fl.ok_post('Callback booked.','The callback could not be booked.'), retries=1),
    [fl.eq('cb_ok','true','fin_callback','booked'),fl.eq('cb_ok','True','fin_callback','booked'),fl.always('callback_fault')],
    mapping=[{'path':'data.ok','variable':'cb_ok'}])
nodes['callback_fault'] = fl.conv('callback_fault','Say the callback could not be booked.',
    on_enter={'type':'tts','text':'I could not book the callback.'}, transitions=[fl.always('fin_no_callback')],first_only=True)

# R15 R16 R17 R19 R48 R51: deterministic identity refusal and human counters.
# API and brief limit coincide; stop_left derived from spec/service allowance.
for stage in ['dob','phone']:
    node = nodes['ask_' + stage]
    node['tools'] = [t for t in node['tools'] if t['name'] != 'transfer_to_agent']
    entry = node['extraction_schema'][0]
    entry['enum'].append('human')
    entry['description'] += ' human = asks for a person or human agent; this is never a security refusal.'
    node['transitions'].append(fl.eq('refusal_' + stage,'human','id_human_' + stage,'request human'))
    node['task_messages'] += " Explain once that security questions protect their account on a refusal, then repeat the question. "
    nodes['id_human_' + stage] = fl.code_node('id_human_' + stage,
        fl.counter_code('human_count', 2, 'id_human_route', reset={'refusal_' + stage:'none'}),[
            fl.eq('id_human_route','close','xfer_general','insists on human'),fl.always('id_help_' + stage)])
    nodes['id_help_' + stage] = fl.conv('id_help_' + stage,
        'Ask once whether you can help first, then continue with the security question. Do not treat the request as refusal.',
        on_enter={'type':'tts','text':'Is there anything I can help you with myself first?'},
        extraction=[fl.ext('help_reply',['continue','human'], 'human = insists on a human; continue = anything else.')],
        transitions=[fl.eq('help_reply','human','xfer_general','insists'),fl.always('ask_' + stage)])
# R37 R58: normalise already-approved code values; never cap amount or date.
record_tool = nodes['record_promise']['pre_actions'][0]
record_tool['pre_process_code'] = fl.normalise_pre({'amount':'amount','date':'date'},date_order='dmy') + "\\n" + record_tool.get('pre_process_code','')

''' + s[i:]
p.write_text(s)

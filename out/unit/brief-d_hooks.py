"""Executes the hooks and the finalize code of out/brief-d.workflow.json on hand-made inputs (offline unit test)."""
import json
wf = json.load(open('out/brief-d.workflow.json'))
N = wf['nodes']
def tool(node, name):
    return [t for t in N[node]['tools'] if t['function']['name'] == name][0]
def code(n):
    return N[n]['pre_actions'][0]['function']['parameters']['properties']['code']['default']
fails = 0
def check(what, got, exp):
    global fails
    ok = got == exp
    fails += not ok
    print(('PASS ' if ok else 'FAIL ') + what, '' if ok else '(got %r, expected %r)' % (got, exp))

# promise_pre: closed day 30 Oct -> 29 Oct; past the deadline -> the deadline; amount above past_due -> past_due
cp = tool('negotiate', 'create_promise')
V = {'pids_csv': 'p1,p2', 'dl_p1': '2026-11-04', 'dl_p2': '2026-10-21', 'pd_p1': '300.0', 'pd_p2': '900.0', 'rec_pids': '', 'note_log': ''}
for body, exp in [({'product_id': 'p1', 'amount': '300', 'date': '2026-10-30'}, '2026-10-29'),
                  ({'product_id': '2', 'amount': '950', 'date': '2026-10-30'}, '2026-10-21'),
                  ({'product_id': 'p1', 'amount': '300', 'date': '2026-10-17'}, '2026-10-16'),
                  ({'product_id': 'p1', 'amount': '300', 'date': '2026-10-26'}, '2026-10-26')]:
    c = {'body': dict(body)}
    exec(cp['pre_process_code'], {'vars': V, 'config': c})
    check('promise_pre %s -> %s' % (body['date'], exp), c['body']['date'], exp)
check('promise_pre id + amount cap', (c['body']['product_id'], ), ('p1',))
c = {'body': {'product_id': '2', 'amount': '950', 'date': '2026-10-21'}}
exec(cp['pre_process_code'], {'vars': V, 'config': c})
check('promise_pre amount capped to past_due', c['body']['amount'], 900.0)

# promise_post: fail, fail, ok -> recorded after the 3rd try; fail x3 -> service_error note
V = {'pids_csv': 'p1', 'rec_pids': '', 'note_log': '', 'pending_pid': 'p1'}
for i in range(2):
    r = {'data': {'ok': False}}
    exec(cp['post_process_code'], {'vars': V, 'result': r})
    check('promise_post fail %d asks a retry' % (i + 1), 'once more' in r['data']['what_to_do_next'], True)
r = {'data': {'ok': True}}
exec(cp['post_process_code'], {'vars': V, 'result': r})
check('promise_post ok on 3rd try records', (V['rec_pids'], V['all_done']), ('p1', 'yes'))
V = {'pids_csv': 'p1', 'rec_pids': '', 'note_log': '', 'pending_pid': 'p1'}
for i in range(3):
    r = {'data': {'ok': False}}
    exec(cp['post_process_code'], {'vars': V, 'result': r})
check('promise_post 3 fails -> service_error note', 'service_error' in r['data']['what_to_do_next'], True)

# verify_post: first wrong -> ask again; second wrong (left 1) -> failed
vp = tool('ask_dob', 'verify_identity')['post_process_code']
for d, exp in [({'ok': True, 'verified': False, 'wrong_answers_left': 2}, 'first'),
               ({'ok': True, 'verified': False, 'wrong_answers_left': 1}, 'FAILED'),
               ({'ok': True, 'verified': False, 'wrong_answers_left': 2, 'hint': 'day_month_swapped'}, 'NOT a wrong answer'),
               ({'ok': True, 'verified': True, 'all_verified': True, 'wrong_answers_left': 2}, 'Identity verified')]:
    r = {'data': dict(d)}
    exec(vp, {'result': r})
    check('verify_post %s' % d, exp in r['data']['what_to_do_next'], True)
fail_tr = [t for t in N['ask_dob']['transitions'] if t['target_node'] == 'fin_failed'][0]
check('ask_dob routes left 1 or 0 to fin_failed', sorted(c['operand'] for c in fail_tr['condition']['conditions']), ['0', '1'])

# finalize precedence: SVC > HSHP > DSP > RF; promise wins; all paid -> AP
fin = code('finalize')
for rec, notes, exp in [('', 'p1:refused,p2:dispute', 'dispute'), ('', 'p1:refused,p2:service_error,p3:hardship', 'service_error'),
                        ('', 'p1:hardship', 'hardship'), ('p1', 'p2:refused,p3:refused', 'promise'), ('', 'p1:paid,p2:paid', 'paid'),
                        ('', 'p1:paid,p2:refused', 'refused'), ('', 'p1:paid,p2:dispute', 'dispute')]:
    V = {'pids_csv': ','.join('p%d' % (i + 1) for i in range(max(1, len([x for x in (rec + ',' + notes).split(',') if x])))), 'rec_pids': rec, 'note_log': notes}
    exec(fin, {'vars': V})
    check('finalize rec=%r notes=%r' % (rec, notes), V['final_route'], exp)
# close codes
for k, oc in [('fin_promise', ('promise', 'PRM')), ('fin_hardship', ('no_promise', 'HSHP')), ('fin_paid', ('paid', 'AP')), ('fin_failed', ('not_verified', 'IDF'))]:
    V = {}
    exec(code(k), {'vars': V})
    check(k, (V['close_outcome'], V['close_code']), oc)
cc = wf['tools'][0]
c = {'body': {'outcome': 'promise', 'reason': 'PRM'}}
exec(cc['pre_process_code'], {'config': c})
check('close_call keeps PRM on promise', c['body'].get('reason'), 'PRM')
print('%d failed' % fails)

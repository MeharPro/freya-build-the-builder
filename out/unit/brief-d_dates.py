"""Executes the setup and prepare code of out/brief-d.workflow.json on the variables and products of the
13 Brief D practice cases and prints the facts the agent will see (offline unit test of the date/floor code)."""
import json, sys
wf = json.load(open('out/brief-d.workflow.json'))
N = wf['nodes']
def src(n):
    return N[n]['pre_actions'][0]['function']['parameters']['properties']['code']['default']
cases = json.load(open('tests/synthetic/brief-d.cases.json'))
for c in cases:
    v = dict(c['variables'])
    exec(src('setup'), {'vars': v})
    v['products'] = [dict(product_id='p%d' % (i + 1), **p) for i, p in enumerate(c['products'])]
    exec(src('prepare'), {'vars': v})
    print(c['id'], v['setup_state'], v['prepare_state'], v['acct_route'])
    print('   ' + v['products_text'].replace('\n', '\n   '))
    print('   expected', c['expected']['promises'])
    if c['id'] in sys.argv[1:]:
        for k in ('statement_text', 'weekday_table', 'callback_text', 'calendar_text', 'vague_text'):
            print('---', k); print(v[k])

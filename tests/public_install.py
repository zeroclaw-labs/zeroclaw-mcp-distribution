"""Verify public acquisition with isolated settings and no registry/Git credentials."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess

ROOT=Path(__file__).resolve().parents[1]
RELEASE=json.loads((ROOT/'release.json').read_text())
REPO='zeroclaw-labs/zeroclaw-mcp-distribution'
VERSION=RELEASE['version']
PACKAGE=f'@zeroclaw-labs/zeroclaw-mcp@{VERSION}'
p=argparse.ArgumentParser()
p.add_argument('route',choices=['npm','marketplaces','bootstrap'])
p.add_argument('--home',type=Path,required=True)
args=p.parse_args()
home=args.home.resolve();home.mkdir(mode=0o700,parents=True)
out=home/'evidence';out.mkdir(mode=0o700)
env={k:v for k,v in os.environ.items() if not k.lower().startswith('npm_config') and k.upper() not in {
 'NPM_TOKEN','NODE_AUTH_TOKEN','GH_TOKEN','GITHUB_TOKEN','SSH_AUTH_SOCK','GIT_ASKPASS','SSH_ASKPASS',
 'OPENAI_API_KEY','ANTHROPIC_API_KEY','CLAUDE_CODE_OAUTH_TOKEN','ACTIONS_RUNTIME_TOKEN',
 'ACTIONS_ID_TOKEN_REQUEST_TOKEN','ACTIONS_ID_TOKEN_REQUEST_URL'}}
for name in ['.npmrc','.npmrc-global','.gitconfig']:
    (home/name).write_text('');(home/name).chmod(0o600)
env.update(HOME=str(home),CODEX_HOME=str(home/'.codex'),CLAUDE_CONFIG_DIR=str(home/'.claude'),
 NPM_CONFIG_CACHE=str(home/'.npm'),NPM_CONFIG_USERCONFIG=str(home/'.npmrc'),
 NPM_CONFIG_GLOBALCONFIG=str(home/'.npmrc-global'),NPM_CONFIG_REGISTRY='https://registry.npmjs.org',
 GIT_CONFIG_GLOBAL=str(home/'.gitconfig'),GIT_CONFIG_NOSYSTEM='1',GIT_TERMINAL_PROMPT='0',
 GH_CONFIG_DIR=str(home/'.config/gh'),XDG_CONFIG_HOME=str(home/'.config'))
for client in ['codex','claude']:(home/f'.{client}').mkdir(mode=0o700)
(home/'.codex/config.toml').write_text('model_reasoning_effort = "low"\n[mcp_servers.unrelated]\ncommand = "/usr/bin/false"\n')
(home/'.claude/settings.json').write_text(json.dumps({'env':{'PUBLIC_ROUTE_SENTINEL':'keep'}}))
(home/'.claude.json').write_text(json.dumps({'mcpServers':{'unrelated':{'command':'/usr/bin/false'}}}))

def run(name,command,timeout=900):
    process=subprocess.Popen(command,cwd=home,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    timed_out=False
    try:
        stdout,stderr=process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out=True
        os.killpg(process.pid,signal.SIGKILL)
        stdout,stderr=process.communicate(timeout=10)
    (out/(name+'.json')).write_text(json.dumps({'exit_code':process.returncode,'timed_out':timed_out,'stdout':stdout,'stderr':stderr},indent=2)+'\n')
    assert not timed_out and process.returncode==0,f'{name} failed; inspect retained evidence'
    return stdout

assert RELEASE['qualified'] is True
assert json.loads(run('npm-integrity',['npm','view',PACKAGE,'dist.integrity','--json'],60))==RELEASE['npm']['integrity']

if args.route=='npm':
    run('npx-install',['npx','--yes',PACKAGE,'install','--codex','--claude'])
    run('npx-repeat',['npx','--yes',PACKAGE,'install','--codex','--claude'])
elif args.route=='marketplaces':
    for client in ['codex','claude']:
        run(client+'-marketplace',[client,'plugin','marketplace','add',REPO,'--json'])
        command=[client,'plugin','add' if client=='codex' else 'install','zeroclaw@zeroclaw-labs','--json']
        run(client+'-install',command)
else:
    url=f'https://github.com/{REPO}/releases/download/v{VERSION}/install.sh'
    script=home/'install.sh'
    run('download-installer',['curl','--fail','--location','--proto','=https','--proto-redir','=https','--connect-timeout','20','--max-time','180','--output',str(script),url],240)
    assert script.read_bytes()==(ROOT/'install.sh').read_bytes()
    run('bootstrap-install',['/bin/sh',str(script),'--codex','--claude'],1200)

codex=json.loads(run('codex-plugins',['codex','plugin','list','--json'],90))['installed']
claude=json.loads(run('claude-plugins',['claude','plugin','list','--json'],90))
c=next(p for p in codex if p['pluginId']=='zeroclaw@zeroclaw-labs')
l=next(p for p in claude if p['id']=='zeroclaw@zeroclaw-labs')
assert c['version']==l['version']==VERSION and c['enabled'] and l['enabled'] and not l.get('errors')
plugin=Path(l.get('readFromFolder') or l['installPath'])
assert plugin.resolve().is_relative_to(home)
proof=json.loads((plugin/'public-provenance.json').read_text())
assert proof['assembly_source_commit']==RELEASE['assemblySource']
assert proof['server_version']==RELEASE['runtimeVersion']
health=run('claude-health',['claude','mcp','list'],120)
assert any('plugin:zeroclaw:zeroclaw:' in line and 'Connected' in line for line in health.splitlines())
run('runtime-probe',['node','-e',
 'require(process.argv[1]).probe(process.argv[2]).then(x=>console.log(JSON.stringify(x))).catch(e=>{console.error(e.message);process.exitCode=1})',
 str(plugin/'installer.cjs'),str(plugin)],120)
assert not (home/'.zeroclaw-manager/registry.json').exists()
assert 'model_reasoning_effort = "low"' in (home/'.codex/config.toml').read_text()
assert 'unrelated' in (home/'.codex/config.toml').read_text()
assert json.loads((home/'.claude/settings.json').read_text())['env']['PUBLIC_ROUTE_SENTINEL']=='keep'
assert 'unrelated' in json.loads((home/'.claude.json').read_text())['mcpServers']
result={'passed':True,'route':args.route,'version':VERSION,'runtime_version':RELEASE['runtimeVersion'],
 'anonymous_acquisition':True,'native_clients':['codex','claude'],'mcp_probe':True,
 'settings_preserved':True,'registry_exists':False,'plugin_path':str(plugin),
 'scope':'Public acquisition, real native client registration/connection and completed MCP probe; no managed-host actions.'}
(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

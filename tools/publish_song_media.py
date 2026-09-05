"""Publish original MP3/MIDI outside Git as immutable GitHub release assets.

Explicit --publish is required. Uses the existing Git credential helper without
printing or persisting its secret. No asset is silently overwritten.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request,urlopen

REPO='marcelozap/malosound'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--date',required=True);p.add_argument('--title',required=True)
    p.add_argument('--mp3',type=Path,required=True);p.add_argument('--midi',type=Path,required=True)
    p.add_argument('--publish',action='store_true')
    args=p.parse_args()
    from datetime import date
    assert date.fromisoformat(args.date).isoformat()==args.date
    assert args.mp3.suffix.lower()=='.mp3' and args.midi.suffix.lower()=='.mid'
    assert args.mp3.is_file() and args.midi.is_file()
    assert args.publish,'Review the files and pass --publish to upload publicly.'
    credential=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,check=True,timeout=30)
    fields=dict(line.split('=',1) for line in credential.stdout.splitlines() if '=' in line)
    token=fields.get('password')
    assert token,'Existing GitHub credential unavailable'
    headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'MaloSound-Publishing','X-GitHub-Api-Version':'2022-11-28'}
    def call(url,method='GET',obj=None,payload=None,content_type='application/json'):
        data=json.dumps(obj).encode() if obj is not None else payload
        request=Request(url,data=data,method=method,headers={**headers,'Content-Type':content_type})
        with urlopen(request,timeout=60) as response:return json.load(response)
    base='https://api.github.com/repos/'+REPO
    tag='spy-song-'+args.date
    try:release=call(base+'/releases/tags/'+tag)
    except HTTPError as exc:
        if exc.code!=404:raise
        # A draft may exist after a prior interrupted upload.
        release=next((r for r in call(base+'/releases?per_page=100') if r['tag_name']==tag),None)
        if release is None:
            release=call(base+'/releases','POST',dict(tag_name=tag,target_commitish='master',name=args.title+' · SPY '+args.date,
                body='Original MaloSound instrumental sketch and editable MIDI, created from the dated SPY regular-session price path. LLM-assisted arrangement and procedural synthesis; 3:15 at 80 BPM. This is musical interpretation, not a trading-performance claim. Analysis and limitations: https://malosound.ai/reports/'+args.date+'-spy-song.html',
                draft=True,prerelease=True))
    urls={}
    for kind,path,ctype in [('mp3',args.mp3,'audio/mpeg'),('mid',args.midi,'audio/midi')]:
        name='spy-'+args.date+'.'+kind;payload=path.read_bytes();digest='sha256:'+hashlib.sha256(payload).hexdigest()
        old=next((z for z in release['assets'] if z['name']==name),None)
        if old:
            assert old['size']==len(payload) and old.get('digest')==digest,'Existing media differs or lacks hash evidence; do not overwrite it.'
            asset=old
        else:
            asset=call(release['upload_url'].split('{')[0]+'?name='+quote(name),'POST',payload=payload,content_type=ctype)
            assert asset['size']==len(payload),'Uploaded size differs'
            if asset.get('digest'):assert asset['digest']==digest,'Uploaded checksum differs'
        urls[kind]=asset['browser_download_url']
    if release['draft']:call(base+'/releases/'+str(release['id']),'PATCH',dict(draft=False))
    published=call(base+'/releases/tags/'+tag)
    assert not published['draft'],'Release is not public'
    # Draft asset URLs contain an untagged identifier; re-read after publishing.
    urls={kind:next(z['browser_download_url'] for z in published['assets'] if z['name']=='spy-'+args.date+'.'+kind) for kind in ('mp3','mid')}
    print(json.dumps({'release':'https://github.com/'+REPO+'/releases/tag/'+tag,'assets':urls},indent=2))


if __name__=='__main__':main()

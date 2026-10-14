#!/usr/bin/env python3
"""Refresh public legacy endpoints from maintained producers, retaining old disks."""
import argparse
import os
from pathlib import Path
import subprocess
from release_assets import Publisher


def download(publisher, asset, path):
    subprocess.run(['curl','--fail','--location','--connect-timeout','15','--max-time','900',
                    '--retry','3','--retry-max-time','180','-o',str(path),asset['browser_download_url']],check=True,timeout=1200)
    if path.stat().st_size!=asset['size']:raise ValueError('source image size mismatch')
    if asset.get('digest') and asset['digest']!='sha256:'+publisher.digest(path):raise ValueError('source image checksum mismatch')


def validate_image(filename):
    environment=os.environ.copy()
    environment.pop('GH_TOKEN',None)
    subprocess.run(['python3','.github/scripts/hosted_image_test.py','--file',str(filename),'--runtime','qemu'],
                   check=True,timeout=4200,env=environment)


ENDPOINTS = {
    'arch': {'source_tag': 'archlinux', 'source_image': 'archlinux-latest.qcow2',
             'image': 'archlinux.qcow2', 'tag': 'v1.0'},
    'alpine': {'source_tag': 'alpine', 'source_image': 'alpine3.22.qcow2',
               'image': 'alpinelinux_stable.qcow2', 'tag': 'v2.0'},
}


def refresh(image):
    endpoint = ENDPOINTS[image]
    source=Publisher('oneclickvirt/pve_kvm_images',os.environ['GH_TOKEN'])
    release=source.request(source.base+'/releases/tags/'+endpoint['source_tag'])
    asset=source.assets(release['id']).get(endpoint['source_image'])
    if not asset or asset.get('state')!='uploaded':raise RuntimeError('maintained public '+image+' image is unavailable')
    filename=Path(endpoint['image']);download(source,asset,filename)
    # Preserve the documented credentials of this legacy consumer endpoint.
    subprocess.run(['sudo','virt-customize','-a',str(filename),'--run-command',
                    "printf 'root:password\n' | chpasswd",'--no-network'],check=True,timeout=600)
    validate_image(filename)
    target=Publisher(os.environ['GITHUB_REPOSITORY'],os.environ['GH_TOKEN'])
    old_release=target.request(target.base+'/releases/tags/'+endpoint['tag'])
    old=target.assets(old_release['id']).get(filename.name)
    if old:
        backup=Path(filename.stem+'-legacy-'+str(old['id'])+'.qcow2')
        download(target,old,backup)
        subprocess.run(['python3','.github/scripts/release_assets.py','legacy-archived',str(backup)],check=True,timeout=1800)
    subprocess.run(['python3','.github/scripts/release_assets.py',endpoint['tag'],str(filename)],check=True,timeout=1800)
    print('Maintained '+image+' image validated and published; previous disk retained in legacy-archived')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', choices=sorted(ENDPOINTS), default='arch')
    refresh(parser.parse_args().image)


if __name__=='__main__':main()

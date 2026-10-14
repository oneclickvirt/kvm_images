#!/usr/bin/env python3
"""Refresh legacy Arch from the public maintained producer, retaining the old disk."""
import os
from pathlib import Path
import subprocess
from release_assets import Publisher


def download(publisher, asset, path):
    subprocess.run(['curl','--fail','--location','--connect-timeout','15','--max-time','900',
                    '--retry','3','--retry-max-time','180','-o',str(path),asset['browser_download_url']],check=True,timeout=1200)
    if path.stat().st_size!=asset['size']:raise ValueError('source image size mismatch')
    if asset.get('digest') and asset['digest']!='sha256:'+publisher.digest(path):raise ValueError('source image checksum mismatch')


def main():
    source=Publisher('oneclickvirt/pve_kvm_images',os.environ['GH_TOKEN'])
    release=source.request(source.base+'/releases/tags/archlinux')
    asset=source.assets(release['id']).get('archlinux-latest.qcow2')
    if not asset or asset.get('state')!='uploaded':raise RuntimeError('maintained public Arch image is unavailable')
    filename=Path('archlinux.qcow2');download(source,asset,filename)
    # Preserve the documented credentials of this legacy consumer endpoint.
    subprocess.run(['sudo','virt-customize','-a',str(filename),'--run-command',
                    "printf 'root:password\n' | chpasswd",'--no-network'],check=True,timeout=600)
    subprocess.run(['python3','.github/scripts/hosted_image_test.py','--file',str(filename),'--runtime','qemu'],check=True,timeout=4200)
    target=Publisher(os.environ['GITHUB_REPOSITORY'],os.environ['GH_TOKEN'])
    old_release=target.request(target.base+'/releases/tags/v1.0')
    old=target.assets(old_release['id']).get(filename.name)
    if old:
        backup=Path('archlinux-legacy-'+str(old['id'])+'.qcow2')
        download(target,old,backup)
        subprocess.run(['python3','.github/scripts/release_assets.py','legacy-archived',str(backup)],check=True,timeout=1800)
    subprocess.run(['python3','.github/scripts/release_assets.py','v1.0',str(filename)],check=True,timeout=1800)
    print('Maintained Arch image validated and published; previous disk retained in legacy-archived')

if __name__=='__main__':main()

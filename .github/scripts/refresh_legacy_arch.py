#!/usr/bin/env python3
"""Refresh public legacy endpoints from maintained producers, retaining old disks."""
import argparse
import os
from pathlib import Path
import subprocess
import shutil
import zipfile
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
    'alpine-edge': {'source_repo': 'oneclickvirt/incus_images',
                    'source_tag': 'kvm_images',
                    'source_image': 'alpine_edge_edge_x86_64_default_kvm.zip',
                    'archive_member': 'disk.qcow2',
                    'image': 'alpinelinux_edge.qcow2', 'tag': 'v2.0'},
    'fedora34': {'source_repo': 'oneclickvirt/kvm_images', 'source_tag': 'v2.0',
                 'source_image': 'fedora34.qcow2', 'image': 'fedora34.qcow2', 'tag': 'v2.0'},
}


def extract_disk(archive_path, filename, member):
    # Extract only the exact producer disk, never arbitrary ZIP paths.
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != {member, 'incus.tar.xz'}:
            raise ValueError('producer archive has an ambiguous disk')
        info = archive.getinfo(member)
        if not 10 * 1024 * 1024 < info.file_size <= 2 * 1024 ** 3:
            raise ValueError('producer disk size is outside release limits')
        if archive.getinfo('incus.tar.xz').file_size > 10 * 1024 * 1024:
            raise ValueError('producer metadata exceeds its size limit')
        if archive.testzip() is not None:
            raise ValueError('producer archive checksum failed')
        with archive.open(info) as source, filename.open('wb') as target:
            shutil.copyfileobj(source, target, 1024 * 1024)
    with filename.open('rb') as disk:
        if disk.read(4) != b'QFI\xfb':
            raise ValueError('producer disk is not QCOW2')


def refresh(image):
    endpoint = ENDPOINTS[image]
    source=Publisher(endpoint.get('source_repo', 'oneclickvirt/pve_kvm_images'),os.environ['GH_TOKEN'])
    release=source.request(source.base+'/releases/tags/'+endpoint['source_tag'])
    asset=source.assets(release['id']).get(endpoint['source_image'])
    if not asset or asset.get('state')!='uploaded':raise RuntimeError('maintained public '+image+' image is unavailable')
    filename=Path(endpoint['image'])
    if endpoint.get('archive_member'):
        archive_path = Path(endpoint['source_image'])
        download(source,asset,archive_path)
        extract_disk(archive_path,filename,endpoint['archive_member'])
    else:
        download(source,asset,filename)
    # Preserve the documented credentials of this legacy consumer endpoint.
    subprocess.run(['sudo','virt-customize','-a',str(filename),'--run-command',
                    "printf 'root:password\n' | chpasswd",'--no-network'],check=True,timeout=600)
    if image == 'fedora34':
        # The original endpoint advertises root/password, but its SSH daemon
        # only offers GSSAPI. Repair that endpoint without changing its OS.
        command = """set -eu
test -s /etc/ssh/sshd_config
for config in /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf; do
  [ -f "$config" ] || continue
  awk '!/^[[:space:]]*(PubkeyAuthentication|PasswordAuthentication|PermitRootLogin)[[:space:]]/' "$config" > "$config.hosted-auth"
  cat "$config.hosted-auth" > "$config"
  rm "$config.hosted-auth"
done
{ printf 'PubkeyAuthentication yes\\nPasswordAuthentication yes\\nPermitRootLogin yes\\n'; cat /etc/ssh/sshd_config; } > /etc/ssh/sshd_config.hosted-repair
chmod 0600 /etc/ssh/sshd_config.hosted-repair
mv /etc/ssh/sshd_config.hosted-repair /etc/ssh/sshd_config
systemctl enable sshd
"""
        subprocess.run(['sudo','virt-customize','-a',str(filename),'--run-command',command,
                        '--selinux-relabel','--no-network'],check=True,timeout=600)
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

# kvm_images

Releases中的镜像：

已预开启安装cloudinit，开启SSH登陆，预设SSH监听V4和V6的22端口，开启允许密码验证登陆

部分镜像开启允许root进行SSH登录

默认用户名：```root```

默认密码：```password```

如果使用务必自行修改密码

目前总的支持的镜像名字(已经过实机验证可使用)

https://github.com/oneclickvirt/kvm_images/blob/main/list.text

每日拉取镜像进行修补和更新的仓库：

https://github.com/oneclickvirt/pve_kvm_images

会支持比较新的一些镜像

## 目录

- [v2.0](#v2.0)
- [v1.1](#v1.1)
- [v1.0](#v1.0)

## v2.0

镜像名称 - 已挂载硬盘大小(开设的虚拟机要比这个数值大)

debian11、debian12 - 2G

ubuntu18、ubuntu20、ubuntu22 - 2G

centos7 - 2G

fedora34 - 5G

alpinelinux_edge、alpinelinux_stable - 2G

rockylinux8 - 4G

centos8-stream - 4G

由于centos8-stream文件过大超过了2G限制，目前存储在朋友的git上

https://api.ilolicon.com/centos8-stream.qcow2

## v1.1

<details>
说明：
  
在v1.0基础上预安装Qemu-guest-agent

镜像名称 - 已挂载硬盘大小(开设的虚拟机要比这个数值大)

debian系 - 2G

ubuntu系 - 2G

</details>

## v1.0

<details>
说明：

镜像名称 - 已挂载硬盘大小(开设的虚拟机的磁盘要大于或等于这个数值)

debian系 - 2G

ubuntu系 - 2G

archlinux系 - 2G

almalinux8 - 10G

fedora33 - 5G

opensuse-leap-15 - 10G

</details>

## 感谢

https://down.idc.wiki/Image/realServer-Template/

提供的原始系统镜像，原始镜像仅开启了cloudinit，其他一切未开启，且不支持root进行SSH登录

## 不要使用

Source code (zip)

Source code (tar.gz) 

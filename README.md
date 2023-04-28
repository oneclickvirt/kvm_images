# Images

Images列表，已预开启安装cloudinit，开启SSH登陆，预设值SSH监听V4和V6的22端口，开启允许密码验证登陆，开启允许ROOT登陆

### 注意

#### debian系，ubuntu系，archlinux系 

上述镜像都没问题

#### centos9-stream centos8-stream centos7 almalinux8 almalinux9 

上述镜像开启允许密码验证登陆和开启允许ROOT登陆失败，待修复

上述系统加载后，需要在PVE的WEB端，找到对应虚拟机的shell或者NOVNC，登陆后切换root权限，执行

```
sed -i 's/#PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config
service ssh restart
service sshd restart
systemctl restart sshd
systemctl restart ssh
```

后修复允许通过密码进行SSH登陆

#### alpine

镜像无能为力，待修复

### 感谢

https://down.idc.wiki/Image/realServer-Template/

提供的原始系统镜像，原始镜像仅开启了cloudinit，其他一切未开启

### 不要使用

Source code (zip)

Source code (tar.gz) 

这两个包，是老的数据，未修改

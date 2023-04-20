#!/usr/bin/bash

# Run unit tests for lvmdbusd on ubuntu/debian

export DEBIAN_FRONTEND="noninteractive"
apt-get update -y -q || exit 1

# install dependencies
apt-get install debhelper-compat autoconf-archive automake libaio-dev libblkid-dev pkg-config systemd \
	thin-provisioning-tools python3-dbus python3-dev python3-pyudev libcmap-dev libcorosync-common-dev \
	libcpg-dev  libdlm-dev libdlmcontrol-dev  libedit-dev libquorum-dev  libsanlock-dev  libselinux1-dev \
	libsystemd-dev  libudev-dev -y -q || exit 1

./configure --enable-dbus-service --enable-notify-dbus --enable-editline || exit 1

make -j12 || exit 1

export LVM_BINARY=`pwd`/tools/lvm
export PYTHONPATH=`pwd`/daemons

cp ./scripts/com.redhat.lvmdbus1.conf /etc/dbus-1/system.d/. || exit 1

truncate -s 1T /d1.disk || exit 1
truncate -s 1T /d2.disk || exit 1
truncate -s 1T /d3.disk || exit 1

dev1=`losetup -f --show /d1.disk`
$LVM_BINARY pvcreate $dev1 || exit 1

dev2=`losetup -f --show /d2.disk`
$LVM_BINARY pvcreate $dev2 || exit 1

dev3=`losetup -f --show /d3.disk`
$LVM_BINARY pvcreate $dev3 || exit 1

python3 daemons/lvmdbusd/lvmdbusd 2>&1 >> /tmp/lvmdbusd.out.txt &

sleep 10

test/dbus/lvmdbustest.py -v || { echo /tmp/lvmdbusd.out ; exit 1;}

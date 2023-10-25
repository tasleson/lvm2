# Copyright (C) 2015-2016 Red Hat, Inc. All rights reserved.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions
# of the GNU General Public License v.2.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import pyudev
import threading
from . import cfg
from .request import RequestEntry
from . import utils

observer = None
observer_lock = threading.RLock()

_udev_lock = threading.RLock()
_udev_count = 0


def udev_add():
	global _udev_count
	with _udev_lock:
		if _udev_count == 0:
			_udev_count += 1

			# Place this on the queue so any other operations will sequence
			# behind it
			r = RequestEntry(
				-1, _udev_event, (), None, None, False)
			cfg.worker_q.put(r)


def udev_complete():
	global _udev_count
	with _udev_lock:
		if _udev_count > 0:
			_udev_count -= 1


def _udev_event():
	utils.log_debug("Processing udev event")
	udev_complete()
	cfg.load()


def known_device(udev_entry):
	# All of these look-ups are all very
	# fast as everything is done in memory with O(1) lookup
	#
	# Note: LVM is using a loopback
	# device and segments it with a number of linear device mapper targets
	# for testing.  The device['DEVNAME'] refers to /dev/dm-N and not the PV path we
	# know about, eg. /dev/mapper/LVMTEST481999pv1 which is a symlink returned by lvm.
	# So we don't have the device in our in memory db, and we don't refresh.  To address
	# this we leverage the device['DEVLINKS'] which includes multiple alias's for the
	# device which includes one that we should know about.
	if 'DEVNAME' in udev_entry:
		if cfg.om.get_object_by_lvm_id(udev_entry['DEVNAME']):
			return True
	if 'DEVLINKS' in udev_entry:
		entries = udev_entry['DEVLINKS'].split()
		for e in entries:
			if cfg.om.get_object_by_lvm_id(e):
				return True
	return False


# noinspection PyUnusedLocal
def filter_event(action, device):
	# Filter for events of interest and add a request object to be processed
	# when appropriate.
	refresh = False

	# Ignore everything but change
	if action != 'change':
		return

	if 'ID_FS_TYPE' in device:
		fs_type_new = device['ID_FS_TYPE']
		if 'LVM' in fs_type_new:
			# If we get a lvm related udev event for a block device
			# we don't know about, it's either a pvcreate which we
			# would handle with the dbus notification or something
			# copied a pv signature onto a block device, this is
			# required to catch the latter.
			if not known_device(device):
				refresh = True
		elif fs_type_new == '':
			# Check to see if the device was one we knew about
			refresh = known_device(device)
	else:
		# This handles the wipefs -a path
		refresh = known_device(device)

	if refresh:
		udev_add()


def add():
	with observer_lock:
		global observer
		context = pyudev.Context()
		monitor = pyudev.Monitor.from_netlink(context)
		monitor.filter_by('block')
		observer = pyudev.MonitorObserver(monitor, filter_event)
		observer.start()


def remove():
	with observer_lock:
		global observer
		if observer:
			observer.stop()
			observer = None
			return True
		return False

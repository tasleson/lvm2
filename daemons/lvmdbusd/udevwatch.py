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
			# Let's skip udev events for LVM devices as we should be handling them
			# with the dbus notifications.
			pass
		elif fs_type_new == '':
			# Check to see if the device was one we knew about
			if 'DEVNAME' in device:
				if cfg.om.get_object_by_lvm_id(device['DEVNAME']):
					refresh = True
	else:
		# This handles the wipefs -a path
		if not refresh and 'DEVNAME' in device:
			if cfg.om.get_object_by_lvm_id(device['DEVNAME']):
				refresh = True

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

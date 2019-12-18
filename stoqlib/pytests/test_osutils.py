import os
from unittest import mock

import pytest

from stoqlib.lib import osutils


@mock.patch('stoqlib.lib.osutils.os.makedirs')
def test_get_application_dir_snap(mock_mkdir, monkeypatch):
    monkeypatch.setenv('SNAP', '/snap/test/')
    monkeypatch.setenv('SNAP_COMMON', '/var/snap/test/common')

    appdir = osutils.get_application_dir()

    assert appdir == '/var/snap/test/common'
    mock_mkdir.assert_called_once_with(appdir)


@mock.patch('stoqlib.lib.osutils.os.makedirs')
def test_get_application_dir_linux(mock_mkdir, monkeypatch):
    monkeypatch.setenv('HOME', 'test_home')
    monkeypatch.setattr(osutils, '_system', 'Linux')

    appdir = osutils.get_application_dir('test')

    assert appdir == os.path.join('test_home', '.test')
    mock_mkdir.assert_called_once_with(appdir)


@mock.patch('stoqlib.lib.osutils.os.makedirs')
def test_get_application_dir_windows(mock_mkdir, monkeypatch):
    monkeypatch.setenv('ALLUSERSPROFILE', 'test_path')
    monkeypatch.setattr(osutils, '_system', 'Windows')

    appdir = osutils.get_application_dir('test')

    assert appdir == os.path.join('test_path', 'test')
    mock_mkdir.assert_called_once_with(appdir)


@mock.patch('stoqlib.lib.osutils.os.makedirs')
def test_get_application_dir_darwin(mock_mkdir, monkeypatch):
    monkeypatch.setenv('HOME', 'test_home')
    monkeypatch.setattr(osutils, '_system', 'Darwin')

    appdir = osutils.get_application_dir('test')

    assert appdir == os.path.join('test_home', 'Library', 'Application Support', 'Stoq')
    mock_mkdir.assert_called_once_with(appdir)


def test_get_application_dir_unknown_system(monkeypatch):
    monkeypatch.setattr(osutils, '_system', 'Unknown')

    with pytest.raises(SystemExit):
        osutils.get_application_dir('test')

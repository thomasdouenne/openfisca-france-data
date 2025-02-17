# -*- coding: utf-8 -*-


# OpenFisca -- A versatile microsimulation software
# By: OpenFisca Team <contact@openfisca.fr>
#
# Copyright (C) 2011, 2012, 2013, 2014, 2015 OpenFisca Team
# https://github.com/openfisca
#
# This file is part of OpenFisca.
#
# OpenFisca is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# OpenFisca is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import os
import logging

from ConfigParser import SafeConfigParser
from pandas import HDFStore

log = logging.getLogger(__name__)

from . import default_config_files_directory


class TemporaryStore(HDFStore):

    @classmethod
    def create(cls, config_files_directory = default_config_files_directory, file_name = None, file_path = None):
        if file_path is None:
            parser = SafeConfigParser()
            config_local_ini = os.path.join(config_files_directory, 'config_local.ini')
            config_ini = os.path.join(config_files_directory, 'config.ini')
            _ = parser.read([config_ini, config_local_ini])
            tmp_directory = parser.get('data', 'tmp_directory')
            if file_name is not None:
                if not file_name.endswith('.h5'):
                    file_name = "{}.h5".format(file_name)
                file_path = os.path.join(tmp_directory, file_name)
            else:
                file_path = os.path.join(tmp_directory, 'temp.h5')
            self = cls(file_path)
            return self

    def extract(self, name = None, variables = None):
        assert name is not None
        data_frame = self[name]
        if variables is None:
            return data_frame
        else:
            return data_frame[variables].copy()
        self.close()
        return data_frame

    def show(self):
        log.info("{}".format(self))
        self.close()

# RuscaWriter — three-column writing editor for non-fiction
# Copyright (C) 2026  Nunzio Curcuruto
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""RuscaWriter — editor di scrittura a tre colonne del progetto RuscaLinux."""
from .model import APP_NAME, APP_VERSION, APP_AUTHOR

__all__ = ["APP_NAME", "APP_VERSION", "APP_AUTHOR", "main"]


def main():
    """Punto di ingresso dell'applicazione."""
    from .editor import main as _main
    return _main()

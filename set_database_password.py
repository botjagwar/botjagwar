import base64
import getpass
import sys

# TODO: FINISH
default_path = "conf/BJDBModule/database_password"
args = sys.argv
set_new_password = False
new_password = None


def parse_args():
    global set_new_password
    global new_password
    for arg in args:
        if arg == '-n':
            set_new_password = True
        if arg.startswith('-pass:'):
            new_password = arg[6:]


class PasswordManager(object):
    """
    Provide secure location to store password
    """
    def __init__(self, password_path=None):
        self.password = None
        if password_path is not None:
            self.password_path = password_path
        else:
            self.password_path = default_path

    def check_database_password(self,):
        if self.password is None:
            return False

    def set_new_db_password(self, new_passwd):
        self.password = new_passwd
        self.write_db_password_file(new_passwd)

    def read_db_password_file(self):
        f = file(self.password_path, 'r')
        try:
            self.password = f.read()
            self.password = self._decrypt(self.password)
        except IOError:
            print "Tsy nahavaky tenimiafina / Password reading failed."
        finally:
            f.close()

    def get_password(self):
        if self.password is None:
            self.read_db_password_file()
        return self.password

    @staticmethod
    def _decrypt(string):
        return base64.decodestring(string)

    @staticmethod
    def _encrypt(string):
        return base64.encodestring(string)

    def write_db_password_file(self, new_password=None):
        """if new_password is None, self.password will be used."""
        f = file(self.password_path, 'w')
        try:
            if new_password is not None:
                f.write(self._encrypt(new_password))
            else:
                f.write(self._encrypt(self.password))
        except IOError as e:
            print e
            print "Tsy nahomby ny fanoatana rakitra tenimiafina vaovao / Failed to write new password to file"

    def run(self):
        valid = self.check_database_password()
        if not valid:
            print "Tsy nahitana tenimiafina / Password file not found."
        self.read_db_password_file()

        if new_password is not None:
            print "Mametraka tenimiafina vaovao / Setting new password."
            self.password = new_password
            self.write_db_password_file(new_password)
        # prompt for new password
        elif self.password is None or set_new_password:
            self.password = getpass.getpass(prompt="Tenimiafina vaovao / New password:")

        # store it encrypted
        self.write_db_password_file()

if __name__ == '__main__':
    parse_args()
    pw_manager = PasswordManager()
    pw_manager.run()

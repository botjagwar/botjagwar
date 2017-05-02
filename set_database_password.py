import base64
import getpass

# TODO: FINISH
default_path = "conf/BJDBModule/database_password"


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

    def read_db_password_file(self):
        f = file(self.password_path, 'r')
        try:
            self.password = f.read()
            self.password = self._decrypt(self.password)
        except IOError:
            print "Tsy nahavaky tenimiafina / Password reading failed."
        finally:
            f.close()

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
            print "Tsy nahomby ny fanoatana rakitra tenimiafina vaovao / Failed to write new password to file"

    def run(self):
        valid = self.check_database_password()
        if not valid:
            print "Tsy nahitana tenimiafina / Password file not found."
        # prompt for new password
        # store it encrypted
        #

if __name__ == '__main__':
    pw_manager = PasswordManager()
    pw_manager.run()

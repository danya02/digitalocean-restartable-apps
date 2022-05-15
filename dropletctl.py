from threading import local
import paramiko
import pathlib
import os

def get_key() -> paramiko.RSAKey:
    """
    Get the application SSH private key, or create one
    """
    try:
        key = paramiko.RSAKey.from_private_key_file('key.rsa')
        return key
    except FileNotFoundError:
        print('Creating SSH key')
        key = paramiko.RSAKey.generate(2048)
        key.write_private_key_file('key.rsa')
        return key

def get_key_publicpart() -> str:
    """
    Get the key's public key string for importing into a remote host
    """
    k = get_key()
    return f'{k.get_name()} {k.get_base64()} digitalocean-restartable-apps.local'

def get_key_fingerprint() -> str:
    """
    Get the key's fingerprint
    """
    k = get_key()
    return k.get_fingerprint().hex(':')

def get_ip_from_droplet_data(droplet_data: dict) -> str:
    """
    Extract the public IP address of a droplet from the "Retrieve Droplet" endpoint data
    """

    # first get the 'v4' and 'v6' net_types
    for net_type in sorted(list(droplet_data['networks'])):
        # for each (first 'v4', then 'v6') net_type, go over elements
        for net in droplet_data['networks'][net_type]:
            # {'ip_address': '12.34.56.78', 'netmask': '255.255.255.0', 'gateway': '12.34.56.0', 'type': 'public'}
            if net['type'] == 'public':
                return net['ip_address']

class DropletConnection:
    """
    SSH connection to a droplet.
    """
    def __init__(self, droplet_data):
        self.droplet_data = droplet_data
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(get_ip_from_droplet_data(droplet_data), username='root', pkey=get_key())
    
    def upload_directory(self, local_dir: pathlib.Path, remote_dir: pathlib.PurePosixPath):
        """
        Upload a directory to the droplet. Missing remote directories will be created,
        and existing files will be overwritten.

        Note that file and directory owners and permissions are not preserved.
        
        Both paths should be pointing to directories; if `local_dir` points to a file, ValueError is raised.
        `remote_dir` must be absolute, or ValueError is raised.
        
        If `local_dir` is `/home/foobar/`, and `remote_dir` is `/foo/bar`,
        and `/home/foobar/test.txt` exists, then it will be uploaded to `/foo/bar/test.txt`.


        """
        if local_dir.is_file():
            raise ValueError('local_dir should be a directory')
        
        if not remote_dir.is_absolute():
            raise ValueError('remote_dir should be an absolute path')
        
        sftp = self.client.open_sftp()

        # Create all parents of the remote directory
        for part in reversed(remote_dir.parents):
            sftp.mkdir(str(part))
        sftp.mkdir(str(remote_dir))

        old_cwd = os.getcwd()
        os.chdir(str(local_dir))
        sftp.chdir(str(remote_dir))

        for root, dirs, files in os.walk('.'):
            # currently in directory `root`, and here are the subdirectories `dirs` and the files `files`
            os.chdir(str(local_dir))
            sftp.chdir(str(remote_dir))
            os.chdir(root)
            sftp.chdir(root)

            for d in dirs:
                sftp.mkdir(d)
            
            for f in files:
                sftp.put(f, f)
        
        os.chdir(old_cwd)
        sftp.close()


    def download_directory(self, remote_dir: pathlib.PurePosixPath, local_dir: pathlib.Path):
        """
        Download a directory from the droplet. Missing local directories will be created,
        and existing files will be overwritten.

        Note that file and directory owners and permissions are not preserved.
        
        Both paths should be pointing to directories; if `local_dir` points to a file, ValueError is raised.
        `remote_dir` must be absolute, or ValueError is raised.
        
        If `local_dir` is `/home/foobar/`, and `remote_dir` is `/foo/bar`,
        and `/foo/bar/test.txt` exists, then it will be downloaded to `/home/foobar/test.txt`.

        This relies on being able to execute `find` on the droplet.
        """
        if local_dir.exists() and not local_dir.is_dir():
            raise ValueError('local_dir should be a directory')
        
        if not remote_dir.is_absolute():
            raise ValueError('remote_dir should be an absolute path')
        
        sftp = self.client.open_sftp()

        # Create all parents of the local directory
        os.makedirs(str(local_dir), exist_ok=True)

        stdin, stdout, stderr = self.client.exec_command('find "' + str(remote_dir) + '" -type f')
        for line in stdout:
            line = line.strip()
            path = pathlib.PurePosixPath(line)
            path_rel = path.relative_to(remote_dir)
            for part in reversed(path.parents):
                part_rel = part.relative_to(remote_dir)
                os.makedirs(str(local_dir / part), exist_ok=True)

            sftp.get(str(path), str(local_dir / path_rel))
        sftp.close()

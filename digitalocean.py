from distutils.command.upload import upload
import SECRETS
import requests
import dropletctl

class DigitalOcean:
    """
    DigitalOcean class for interacting with the DigitalOcean API
    """

    # Droplets that have this tag will be deleted by the `autodelete` methods.
    # By default, `create_droplet` will add this tag to new droplets, unless
    # `no_autodelete` is set to True.
    # This tag contains a UUID so that it does not accidentally collide with any user tags.
    AUTODELETE_TAG = 'autodelete:6ecca9bf-ac35-41bc-abee-1bd96ad5fdef'

    def __init__(self, token=SECRETS.DIGITALOCEAN_ACCESS_TOKEN):
        self.token = token
        self.session = requests.session()
        self.session.headers.update({'Authorization': 'Bearer ' + self.token})

    def list_droplets(self, page=1):
        """
        Get a list of droplets
        """

        url = 'https://api.digitalocean.com/v2/droplets'
        params = {'page': page}
        response = self.session.get(url, params=params)
        return response.json().get('droplets')
    
    def get_regions(self):
        """
        Get a list of regions for droplets
        """    
        url = 'https://api.digitalocean.com/v2/regions'
        response = self.session.get(url, params={'per_page': 200})
        return response.json().get('regions')

    def get_images(self, type='distribution', page=1):
        """
        Get a list of usable droplet images
        """
        url = 'https://api.digitalocean.com/v2/images'
        params = {'type': type, 'per_page': 200, 'page': page}
        response = self.session.get(url, params=params)
        return response.json().get('images')
    
    def get_sizes(self):
        """
        Get a list of droplet sizes
        """
        url = 'https://api.digitalocean.com/v2/sizes'
        response = self.session.get(url)
        return response.json().get('sizes')
    
    def get_default_key_id(self):
        """
        Get the ID of the default application SSH key (from `dropletctl.get_key()`).
        If this key is not yet imported into DigitalOcean, import it.
        """
        key_fingerprint = dropletctl.get_key_fingerprint()
        existing_key_req = self.session.get('https://api.digitalocean.com/v2/account/keys/' + key_fingerprint)
        if existing_key_req.status_code == 200:
            return existing_key_req.json().get('ssh_key').get('id')
        else:
            key_str = dropletctl.get_key_publicpart()
            data = {
                'name': 'DigitalOcean Restartable Apps key',
                'public_key': key_str
            }
            upload_key_req = self.session.post('https://api.digitalocean.com/v2/account/keys', json=data)
            upload_key_req.raise_for_status()
            return upload_key_req.json().get('ssh_key').get('id')


    def create_droplet(self, name, region, size='s-1vcpu-1gb', image='ubuntu-21-10-x64',
                       ssh_keys=None, monitoring=False, backups=False, tags=None,
                       no_autodelete=False, no_default_ssh_key=False,
                       user_data=None):
        """
        Create a new droplet

        If `no_autodelete` is False, the droplet will be tagged with the `autodelete` tag,
        which means that `autodelete()` will delete it.
        To avoid this, set `no_autodelete` to True.

        If `no_default_ssh_key` is False, then in addition to the `ssh_keys` specified,
        the key from `dropletctl.get_key()` will be added to the droplet.
        To avoid this, set `no_default_ssh_key` to True.
        """
        url = 'https://api.digitalocean.com/v2/droplets'
        data = {
            'name': name,
            'region': region,
            'size': size,
            'image': image,
            'backups': backups,
            'monitoring': monitoring,
            'tags': (tags or []) + ([self.AUTODELETE_TAG] if not no_autodelete else []),
            'ssh_keys': (ssh_keys or []) + ([self.get_default_key_id()] if not no_default_ssh_key else [])
        }
        if user_data:
            data['user_data'] = user_data
        response = self.session.post(url, json=data)
        return response.status_code, response.json()


    def autodelete(self):
        """
        Delete ALL droplets that have the `autodelete` tag
        """

        url = 'https://api.digitalocean.com/v2/droplets'
        params = {'tag_name': self.AUTODELETE_TAG}
        response = self.session.delete(url, params=params)
        return response.status_code == 204

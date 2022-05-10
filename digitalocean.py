import SECRETS
import requests

class DigitalOcean:
    """
    DigitalOcean class for interacting with the DigitalOcean API
    """

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
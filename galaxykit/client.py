"""
client.py contains the wrapping interface for all the other modules (aside from cli.py)
"""
from simplejson.errors import JSONDecodeError
from simplejson import dumps
import sys
from urllib.parse import urlparse, urljoin

import requests

from . import dockerutils
from . import users
from . import groups


class GalaxyClient:
    """
    The primary class for the client - this is the authenticated context from
    which all authentication flows.
    """

    headers = None
    galaxy_root = ""
    token = ""
    docker_client = None

    def __init__(self, galaxy_root, auth=None, container_engine=None, container_registry=None):
        self.galaxy_root = galaxy_root
        self.headers = {}

        if auth:
            username, password = auth
            resp = requests.post(galaxy_root + "v3/auth/token/", auth=(user, password))
            try:
                self.token = resp.json().get("token")
            except JSONDecodeError as e:
                print(f"Failed to fetch token: {resp.text}", file=sys.stderr)
            self.headers.update({
                "Accept": "application/json",
                "Authorization": f"Token {self.token}",
            })

            if container_engine:
                container_registry = container_registry or \
                    urlparse(self.galaxy_root).netloc.split(":") + ":5001"

                self.docker_client = dockerutils.DockerClient(
                    (user, password), container_engine, container_registry
                )
    
    def _http(self, method, path, *args, **kwargs):
        url = urljoin(self.galaxy_root, path)
        headers = kwargs.pop("headers", self.headers)
        resp = requests.request(method, url, headers=headers, *args, **kwargs)
        try:
            json = resp.json()
        except JSONDecodeError as e:
            print(resp.text)
            raise ValueError("Failed to parse JSON response from API")
        if "errors" in resp:
            # {'errors': [{'status': '403', 'code': 'not_authenticated', 'title': 'Authentication credentials were not provided.'}]}
            raise Exception(resp["errors"][0]["title"])
        return json
    
    def _payload(self, method, path, body, *args, **kwargs):
        if isinstance(body, dict):
            body = dumps(body)
        if isinstance(body, str):
            body = body.encode('utf8')
        headers = {
            **kwargs.pop("headers", self.headers),
            "Content-Type": "application/json;charset=utf-8",
            "Content-length": str(len(body)),
        }
        kwargs["headers"] = headers
        kwargs["data"] = body
        return self._http(method, path, *args, **kwargs)
    
    def get(self, path, *args, **kwargs):
        return self._http("get", path, *args, **kwargs)

    def post(self, *args, **kwargs):
        return self._payload("post", *args, **kwargs)
    
    def put(self, *args, **kwargs):
        return self._payload("put", *args, **kwargs)

    def pull_image(self, image_name):
        """pulls an image with the given credentials"""
        return self.docker_client.pull_image(image_name)

    def tag_image(self, image_name, newtag, version="latest"):
        """tags a pulled image with the given newtag and version"""
        return self.docker_client.tag_image(image_name, newtag, version=version)

    def push_image(self, image_tag):
        """pushs a image"""
        return self.docker_client.push_image(image_tag)

    def get_or_create_user(
        self, username, password, group, fname="", lname="", email="", superuser=False
    ):
        """
        Returns a "created" flag and user info if that already username exists,
        creates a user if not.
        """
        return users.get_or_create_user(
            self,
            username,
            password,
            group,
            fname,
            lname,
            email,
            superuser,
        )
    
    def get_user_list(self):
        return users.get_user_list(self)

    def delete_user(self, username):
        """deletes a user"""
        return users.delete_user(self, username)

    def create_group(self, group_name):
        """
        Creates a group
        """
        return groups.create_group(self, group_name)

    def find_group(self, group_name):
        """
        Returns the data of the group with group_name
        """
        return groups.find_group(self, group_name)

    def delete_group(self, group_name):
        """
        Deletes the given group
        """
        return groups.delete_group(self, group_name)

    def set_permissions(self, group_name, permissions):
        """
        Assigns the given permissions to the group
        """
        return groups.set_permissions(
            self, group_name, permissions
        )

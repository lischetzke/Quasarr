# Development Setup for Pull Requests

To test your changes before submitting a pull request:

**Run Quasarr with the `--internal_address` parameter:**

```bash
python Quasarr.py --internal_address=http://<host-ip>:<port>
```

Replace `<host-ip>` and `<port>` with the scheme, IP, and port of your host machine.
The `--internal_address` parameter is **mandatory**.

**Start the required services using the `dev-services-compose.yml` file:**

```bash
CONFIG_VOLUMES=/path/to/config docker-compose -f docker/dev-services-compose.yml up
```

Replace `/path/to/config` with your desired configuration location.
The `CONFIG_VOLUMES` environment variable is **mandatory**.

# Development Setup for Pull Requests

To test your changes before submitting a pull request:

**1. Prepare your Environment with `uv`**

Ensure you have the development tools (like `ruff`) installed and your environment synced:

```bash
uv sync --group dev
```

Install the pre-commit hook that ensures linting, formatting and version upgrades through pre-commit.py

```bash
uv run pre-commit install
```

**2. Run Quasarr with the `--internal_address` parameter**

```bash
uv run Quasarr.py --internal_address=http://<host-ip>:<port>
```

Replace `<host-ip>` and `<port>` with the scheme, IP, and port of your host machine.
The `--internal_address` parameter is **mandatory**.

**3. Start the required services using the `dev-services-compose.yml` file**

```bash
CONFIG_VOLUMES=/path/to/config docker-compose -f docker/dev-services-compose.yml up
```

Replace `/path/to/config` with your desired configuration location.
The `CONFIG_VOLUMES` environment variable is **mandatory**.

---

### Code Quality & Maintenance

The CI pipeline enforces strict code styling and import optimization. Please run this commands before pushing your
changes. Alternatively, you should just set up the pre-commit hook as described above.

**Format code AND upgrade dependencie manually:**

```bash
uv run pre-commit.py --upgrade
```

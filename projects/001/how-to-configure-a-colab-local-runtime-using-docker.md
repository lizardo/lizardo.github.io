---
title: How to configure a Colab local runtime using Docker
---

***

**NOTE: This text has been automatically extracted from a [Colab/Jupyter notebook](https://colab.research.google.com/drive/1sRkj7_VbLp8oguD8OmD6-ZXEH2LBJwe1#revisionId=0BzK9MbvobeYaR2NGKzlmYjVBUjZXZ2piQ2FadVQ0UmRPMzZzPQ){:target="_blank"}. If you have any questions, feel free to leave a comment there (requires sign in with a Google account).**

***

In this notebook, I describe the steps I use for running Colab notebooks with a [local runtime](https://research.google.com/colaboratory/local-runtimes.html). I diverge from the official instructions mainly because I prefer to run the Jupyter software inside a Docker container, for safety reasons.

For documentation and learning purposes, I will describe the rationale behind the procedures. If you are only interested in running the procedure, skip to the [Usage](#usage) section.

If you have any questions, please leave a comment on this notebook (if you sign in with a Google account, there should be a **💬 Comment** button on the upper right corner). So far, I have only tested this procedure on Linux. I would really appreciate any feedback on following it on Mac OS and/or Windows!

## Pre-requisites

I assume you have already installed:

1. [Docker](https://docs.docker.com/get-docker/)
2. [Python](https://www.python.org/downloads/)

Additionally, I assume you have a basic knowledge on how to use the command line (terminal) on your computer.

## The setup script

> _**NOTE**: the cells on this section are not meant to be run directly on Colab. They are simply a convenient way to write Python code interleaved with documentation that can be easily downloaded._

We will need the following modules:

```python
import os
import secrets
from subprocess import run, check_call, CalledProcessError, DEVNULL
```

<a name="docker-name"></a>
We will also need a name. It will be used in several Docker container components:

- name
- hostname
- volume (with `-data` appended)
- image (with `-img` appended), if using encryption

```python
name = 'local-jupyter-runtime'
```

<br>

---

**Creating an encrypted "data" directory**

This is an optional step, but recommended if you intend to manipulate sensitive files. If you don't have whole disk encryption, the directory where Docker saves volumes (`/var/lib/docker`) will NOT be encrypted. To remediate this, we will use [gocryptfs](https://github.com/rfjakob/gocryptfs) to configure an encrypted **data** directory.

First, we define a function which:
- creates a file containing the encryption password (16 random characters)
- builds a Docker image containing gocryptfs
- adds extra parameters to `docker run`

```python
extra_docker_args = []
docker_image = 'jupyter/base-notebook'

dockerfile_encryption = """
FROM jupyter/base-notebook

USER root

# It is faster to download the fuse package manually than to install it through
# apt. Additionally, gocryptfs is outdated on Ubuntu Focal (base image for
# jupyter/base-notebook).

ENV pkg_mirror=http://mirrors.kernel.org/ubuntu
ENV fuse_deb_url=${pkg_mirror}/pool/main/f/fuse/fuse_2.9.9-3_amd64.deb
ENV gh_release=https://github.com/rfjakob/gocryptfs/releases/download/v2.1
ENV gocryptfs_tgz_url=${gh_release}/gocryptfs_v2.1_linux-static_amd64.tar.gz

# FIXME: Check PGP signatures for fuse & gocryptfs
RUN wget -O- ${fuse_deb_url} | dpkg --fsys-tarfile - | \
    tar -C /usr/local/bin -xf- --strip-components=2 ./bin/fusermount
RUN chown root /usr/local/bin/fusermount && \
    chmod u+s /usr/local/bin/fusermount
RUN wget -O- ${gocryptfs_tgz_url} | tar -C /usr/local/bin -xzf- gocryptfs

USER jovyan
"""

def setup_encryption(keyfile):
    global extra_docker_args
    global docker_image

    # Source: https://stackoverflow.com/a/49021109
    mount_arg = f'type=bind,src={os.path.abspath(keyfile)},' + \
                f'dst=/home/jovyan/{keyfile},readonly'
    extra_docker_args = ['--device', '/dev/fuse',
                         '--cap-add', 'SYS_ADMIN',
                         '--security-opt', 'apparmor:unconfined',
                         '--mount', mount_arg]
    docker_image = f'{name}-img'

    if not os.path.exists(keyfile):
        open(keyfile, 'w').write(secrets.token_urlsafe(16))
        print(f'Created encryption key file: {keyfile}')

    run(['docker', 'build', '-t', docker_image, '-'], check=True,
        input=dockerfile_encryption, universal_newlines=True)
```

Next, we call the function to perform the setup:

```python
setup_encryption('cipher.key') # Add "#" before this line to disable encryption
```

If you do not want encryption, comment out the line above (i.e. put `#` at the beginning of the line before saving this notebook as a script).

<br>

---

This POSIX shell script snippet will run inside the container, and will:

- Mount an encrypted directory under **data** (if previously enabled)
- Make adjustments that allow notebooks to install local software, including Python packages
- Configure the `jupyter_http_over_ws` Jupyter extension
- Start the notebook with required parameters

The last two points come from the [official instructions](https://research.google.com/colaboratory/local-runtimes.html) for using a local runtime with Colab.

```python
# NOTE: The "cipher.key" file will remain readable by any process running
# inside the container. This is not a problem, as files protected by encryption
# are also accessible anyway.
start_notebook = """
if [ -f cipher.key ]; then
    mkdir -p data
    log_file=/tmp/gocryptfs.log
    error_file='data/!!!ERROR_NOT_ENCRYPTED!!!.txt'
    rm -f "${error_file}" ${log_file}
    gocryptfs_cmd='timeout -v 10 gocryptfs -nosyslog -passfile cipher.key'
    if [ ! -d cipher ]; then
        mkdir cipher
        ${gocryptfs_cmd} -init cipher > ${log_file} 2>&1
    fi
    ${gocryptfs_cmd} cipher data >> ${log_file} 2>&1
    if [ $? -eq 0 ]; then
        if [ ! -f data/README.gocryptfs.txt ]; then
            cat ${log_file} > data/README.gocryptfs.txt
        fi
    else
        cat ${log_file} > "${error_file}"
    fi
fi

mkdir -p ${HOME}/.local/bin && export PATH=${PATH}:${HOME}/.local/bin &&
mkdir -p `python -m site --user-site` &&
pip install jupyter_http_over_ws &&
jupyter serverextension enable --py jupyter_http_over_ws &&
start-notebook.sh \
    --NotebookApp.allow_origin=https://colab.research.google.com \
    --port=8888 \
    --NotebookApp.port_retries=0
"""
```

Try to start an existing (stopped) container. If it fails, run a new one:

```python
try:
    check_call(['docker', 'start', name], stdout=DEVNULL, stderr=DEVNULL)
except CalledProcessError:
    check_call(['docker', 'run', '--detach', '--publish', '8888:8888',
               '--name', name, '--hostname', name,
               '--mount', f'type=volume,src={name}-data,dst=/home/jovyan'] +
               extra_docker_args +
               [docker_image, 'sh', '-c', start_notebook],
               stdout=DEVNULL)
```

To understand the meaning of the various parameters given to `docker run`, see the [Docker documentation](https://docs.docker.com/engine/reference/run/).

We need to obtain the **Backend URL**. This step is a bit more complicated because we need to wait for the container to start fully. For this, we make several validations:

- Is there a running process for the notebook?
- Is there a JSON file corresponding to this process?
- Is the URL stored on the JSON file accessible? Does it authenticate?

The following POSIX shell script does all these validations:

```python
get_backend_url = """
until pgrep -f ${CONDA_DIR}/bin/jupyter-notebook >/dev/null; do
    echo Waiting PID...
    sleep 1
done
nbserver_pid=`pgrep -f ${CONDA_DIR}/bin/jupyter-notebook`
nbserver_config=.local/share/jupyter/runtime/nbserver-${nbserver_pid}.json
until [ -f ${nbserver_config} ]; do
    echo Waiting JSON...
    sleep 1
done
backend_url() {
    awk -F\\" "\\$2 == \\"token\\" {
        print \\"http://localhost:8888/?token=\\" \\$4
    }" ${nbserver_config}
}
until wget -q -O- `backend_url` | grep -q "<title>Home Page"; do
    echo Waiting URL...
    sleep 1
done
echo Backend URL: `backend_url`
"""
```

Finally, run the above snippet, which will print the Backend URL:

```python
check_call(['docker', 'exec', name, 'sh', '-c', get_backend_url])
```

<a name="usage"></a>
## Usage


1. Download this notebook as a Python script: **File ▶ Download ▶ Download .py**
2. Open a terminal, go to the directory where you saved the script, and run: `python3 colablocalruntime.py`
3. Wait until the **Backend URL** is displayed.

This URL will be valid while the container is not restarted. If you forget or Colab asks for the URL again, re-run the script as shown in step 2.

### Connecting to a local runtime

1. Open the notebook you want to use a local runtime with.
2. Click on the **down arrow** next to the **Connect ▼** button (upper right corner).
3. Click on the **Connect to a local runtime** option. A "Local connection settings" dialog box will open.
4. On the **Backend URL** text field, paste the URL obtained from the steps above.
5. Optionally, if you are handling sensitive information and do not want to have the output saved on Google servers, be sure to the check the **☑ Omit code cell output when saving this notebook**.
6. Click on **Connect**.

If everything worked as expected, the "Connect" button will change to: **✅ Connected (Local) ▼** (i.e. a green heavy check mark).

### Quick validation

If you want to confirm the local runtime is working properly, follow the previous steps, connecting this notebook to it, and **run this cell**:

```
%%bash
echo ${HOSTNAME}
```

If it prints the same value shown on the ["name" variable shown earlier](#docker-name), we are all good!

## Appendix: known issues

- Colab "Files" view (the folder icon at the left side bar) will show files inside the container. You can delete and upload files, but if you try to open a file (double-click it), Colab will show a "403 Forbidden" error. This is apparently a [bug from Jupyter](https://github.com/jupyterlab/jupyterlab/issues/7539). The file is accessible from code cells though.
- Encryption support probably only works on Linux hosts.

## Appendix: further help installing Docker on Linux

The official Docker installation documentation for Linux may seem confusing. Therefore, you can follow this guide to navigate through the documentation:

1. Go to the **[Server](https://docs.docker.com/engine/install/#server)** section (*even though you are on a Desktop!*): 
2. Click on the corresponding link for your distribution.
3. Scroll down to the **Install using the convenience script** section.

There you will find how to use the [convenience script](https://get.docker.com/), which automates all the steps needed for our basic Docker usage.


## Appendix: deleting the local runtime

If you need to delete the local runtime for some reason, follow these instructions:

```shell
name=local-jupyter-runtime
docker stop ${name}
docker rm ${name}
docker volume rm ${name}-data
docker image rm ${name}-img
```

This POSIX shell script will:
- Stop the container (if running)
- Remove the container
- Remove the persistent volume
- Remove the image

Note that, after this last step, **Any data saved inside the local runtime will be deleted forever**.

<!-- Generated with ipynbtomarkdown.py -->

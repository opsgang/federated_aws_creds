# Why Docker?

Why wasn't this a pip package, or just a set of install instructions?

Why a bash script that calls a docker image that runs a python script?

Seems unnecessarily complicated, no?

If I could it'd be delivered as a golang binary.
But golang doesn't have ready support for NTLM over HTTPS yet.

I considered making it a XAR executable, but that requires just
a bit too much varied set up depending on the user's environment.

_sigh_.

I opted for docker because I was tired of getting the awsaml.py script
working on the diverse range of other people's local environments.

Which python did they have? Could I install 3.x as well as 2.7 (or 2.6)
with out clobbering their system?

Would I be able to ensure their system had the required C libs with out
doing additional harm?

Did they need virtual env, so I could make sure the pip-installed libs
were versions that wouldn't impact other python apps?

Ultimately dockerising the script gave me _isolation_ for the execution
environment and all of those issues went away.

The bash script is not required - its just a wrapper to run the docker.

You could equally just run

```bash
docker run --rm -it \
    --name els_aws_creds \
    -v $HOME/.aws:/root/.aws \
        federated-aws-creds:stable
```

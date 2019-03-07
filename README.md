# federated-aws-creds

>
> Get AWS creds suitable for use with terraform, aws cli etc ...
>
> Interactively assume an AWS role based on an AD group.
>
> By default creds are written to your ~/.aws dir as AWS profiles.
>
> However you can also export them as env vars, which is better
> for some operations e.g. using terraform.
>

*Contents:*

* [1st time setup](#1st-time-setup-upgrade)

* [usage](#usage)

* [building (docker image)](#building)

* [older images / rollback](#older-images-rollback)

* [running the image manually](#running-the-image-manually)

* [other use cases](#use-cases)

## 1st TIME SETUP / UPGRADE

You need docker. And bash.

Clone this repo and `cd` to it:

```bash
# first time setup only
mkdir -p $HOME/.aws
cp ./aws-creds.sh $HOME/.aws/
if ! grep "^ *\. .*/.aws/aws-creds.sh" $HOME/.bashrc >/dev/null
then
    echo -e ". $HOME/.aws/aws-creds.sh\n" >> $HOME/.bashrc
fi
. $HOME/.aws/aws-creds.sh

cat << EOF
SETUP COMPLETE.
Any other existing shell sessions must be restarted, or else
source $HOME/.aws/aws-creds.sh in them.
EOF
```

## USAGE

If you've followed first time setup, you can now use the
`aws_creds` command.

```bash

# first, set the URL for AD auth:

export IDP_URL="https://example.com/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices"

aws_creds # run interactively

aws_creds --help # ... check it out to see what else you can do.

aws_creds --export # ... set my creds as AWS_* env vars

```

You can reduce the interaction chores by presetting some env vars
>
> Pro tip: run `aws_creds --help` for the full list
>

```bash
export IDP_URL="https://example.com/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices"
export AD_USER=smithj
export AWS_ROLE_ARN=arn:aws:iam::321987654321:role/ADFS-EnterpriseAdmin

aws_creds # will assume admin role if available for user $AD_USER
```

Or wrap these in to your own bashrc functions to make life
even easier ...

```bash
export IDP_URL="https://example.com/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices"
export AD_USER=smithj
admin_creds() {
    AWS_ROLE_ARN=arn:aws:iam::123456789123:role/ADFS-EnterpriseAdmin \
        aws_creds "$*" # can still pass --export etc ...
}

dev_creds() {
    AWS_ROLE_ARN=arn:aws:iam::123456789123:role/ADFS-Developer \
        aws_creds "$*" # can still pass --export etc ...
}

readonly_creds() {
    AWS_ROLE_ARN=arn:aws:iam::123456789123:role/ADFS-ReadOnly \
        aws_creds "$*" # can still pass --export etc ...
}
```

## BUILDING

The docker image should live in a registry with anonymous access, not AWS ECR
- as we need AWS creds already to get the image that is meant to provide us
with AWS creds ... chicken, meet egg.

To build, just run `build.sh`

Test the image. Once you are satisfied tag it as `stable`, and push to the
remote repository.

e.g. if we are using dockerhub

```
./build.sh

# now test the image
# then get ready to push ...
L_IMG=federated-aws-creds:candidate
R_IMG=federated-aws-creds
DATETIME=$(date '+%Y%m%d%H%M%S')
docker tag $L_IMG $R_IMG:$DATETIME
docker tag $L_IMG $R_IMG:stable
docker push $R_IMG:$DATETIME
docker push $R_IMG:$stable
```

## OLDER IMAGES / ROLLBACK

Older images are not overwritten - they are available using their
datetime tags.

To use any alternative image with `aws_creds` shell function
set the DOCKER\_IMAGE env var before invoking it.

>
> check out `aws_creds --help` for more info.
>

## RUNNING THE IMAGE MANUALLY

Effectively to run the script in full interactive mode, you could
instead run this:

```bash
docker rm -f aws_creds ;
docker run --rm -it \
    --name aws_creds \
    -v $HOME/.aws:/root/.aws \
        federated-aws-creds:stable
```

## EXAMPLE USE CASES

## getting docker images from ECR

You need AWS creds to access ECR.

You also need to log in to the ECR registry before you can pull or push.

So consider this helper function:

```bash
pull_from_ecr() {
    # ... try to get docker login creds.
    # On fail, assume we need fresh aws creds first and retry.
    [[ -z "$1" ]] && echo >&2 "... pass an image name" && return 1
    local img="$1"
    if ! cmd=$(aws ecr get-login --no-include-email)
    then
        aws_creds --export || return 1
        cmd=$(aws ecr get-login --no-include-email) || return 1
    fi
    $(echo "$cmd")
    docker pull $img
}
```

Naturally you could combine this with other helper functions to reduce
the interaction required, as suggested in the [Run](#running) section.

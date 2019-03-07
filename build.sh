#!/bin/bash
# vim: et sr sw=4 ts=4 smartindent:

export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-eu-west-1}"

DOCKERFILE=Dockerfile
GIT_SHA_LEN=8
IMG_TAG=candidate

built_from(){
    (
        set -o pipefail;
        grep -Po '(?<=^FROM )\s*\S+' $DOCKERFILE | head -n 1 | sed -e 's/^s+//'
    )
}

built_by() {
    local user="--UNKNOWN--"
    if [[ ! -z "${BUILD_URL}" ]]; then
        user="${BUILD_URL}"
    elif user="$(aws sts get-caller-identity --query 'Arn' --out text 2>/dev/null)"
    then
        user=$user@$HOSTNAME
    elif user="$(aws iam get-user --query 'User.UserName' --out text 2>/dev/null)"
    then
        user=$user@$HOSTNAME
    else
        user="$(git config --get user.name)@$HOSTNAME"
    fi
    echo "$user" | sed -e 's/ /_/g'
}

git_uri(){
    git config remote.origin.url || echo 'no-remote'
}

git_sha(){
    git rev-parse --short=${GIT_SHA_LEN} --verify HEAD
}

git_branch(){
    r=$(git rev-parse --abbrev-ref HEAD)
    [[ -z "$r" ]] && echo "ERROR: no rev to parse when finding branch? " >&2 && return 1
    [[ "$r" == "HEAD" ]] && r="from-a-tag"
    echo "$r"
}

img_name(){
    (
        set -o pipefail;
        grep -Po '(?<=LABEL [nN]ame=")[^"]+' $DOCKERFILE | head -n 1
    )
}

labels() {
    bf=$(built_from) || return 1
    bb=$(built_by) || return 1
    gu=$(git_uri) || return 1
    gs=$(git_sha) || return 1
    gb=$(git_branch) || return 1
    gt=$(git describe --exact-match 2>/dev/null || echo "no-git-tag")

    cat<<EOM
    --label opsgang.build_date=$(date '+%Y%m%d%H%M%S')
    --label opsgang.built_from=$bf
    --label opsgang.build_git_uri=$gu
    --label opsgang.build_git_sha=$gs
    --label opsgang.build_git_branch=$gb
    --label opsgang.build_git_tag=$gt
    --label opsgang.built_by=$bb
EOM
}

docker_build(){

    labels=$(labels) || return 1
    echo "INFO $0: will add these labels to image:"
    echo "$labels"

    n="$(img_name):$IMG_TAG" || return 1

    echo "INFO $0: building image $n"
    docker build -f $DOCKERFILE --force-rm $labels -t $n .
}

docker_build

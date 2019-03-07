# vim: et sr sw=4 ts=4 smartindent syntax=sh:
# source this file, don't run
[[ "${BASH_SOURCE[0]}" == "${0}" ]] && echo >&2 "ERROR ... source $0, don't execute." && exit 1

# ... env vars that user can set, which are honoured by
_USER_OPTS="
    AD_USER
    AD_PWD
    AWS_DEFAULT_REGION
    AWS_DIR
    AWS_ROLE_ARN
    IDP_URL
"

# aws_creds(): ... user function to run
aws_creds() {

    local rc=0
    local export_creds=""

    local default_aws_dir="$HOME/.aws"
    local default_img="federated-aws-creds:candidate"

    local aws_dir="${AWS_DIR:-$default_aws_dir}"
    local els_creds_img="${DOCKER_IMAGE:-$default_img}"
    local DEBUG=""
    # -h || --help
    [[ "$*" =~ (\-h( |$)|-+help) ]] && __usage && return 0
    # --export
    [[ "$*" =~ \-\-export ]] && export_creds="y"

    # --debug
    [[ "$*" =~ \-\-debug ]] && DEBUG=true

    debug_summary

    __prep_env "$els_creds_img" "$aws_dir" || return 1

    env_str=$(__docker_env_opts)

    __run_docker "$els_creds_img" "$aws_dir" "$env_str" || return 1

    [[ -z "$export_creds" ]] || . $aws_dir/exportawsvars.sh

}

debug_summary() {
    __d "... will use:"
    __d "  IMAGE: $els_creds_img"
    __d "AWS DIR: $aws_dir"
}

__run_docker() {
    local els_creds_img="$1"
    local aws_dir="$2"
    local env_str="$3"

    local fn="${FUNCNAME[0]}()"
    local pfn="${FUNCNAME[1]}()"
    local rc=0

    local container_name="aws_creds-$(date '+%Y%m%d%H%M%S')"

    # ... container must run interactively
    docker run --rm -it \
        --name "$container_name" \
        -v $aws_dir:/root/.aws \
        $env_str $els_creds_img || rc=1

    [[ $rc -ne 0 ]] && echo "ERROR $fn (from $pfn): ... unable to run $img"

    # ... clean up regardless
    docker rm -f $container_name >/dev/null 2>&1
    return $rc
}

__usage() {
    cat <<EOF
usage: aws_creds [--export || --help] [--debug]

Interactively provides AWS creds (e.g. for use with AWS CLI) based on
your Active Directory account permissions.

Creds are written to a profile in your AWS dir.
Can be optionally exported as env vars (--export).

ARGS
====
    --export: ... will export your AWS creds in to your shell as env vars.
    --debug: ... prints extra execution info to STDERR
    --help || -h: ... prints this usage info.

USER OPTS - ENV VARS
====================
The following env vars can be set before running the function:

AWS_DIR: Default: \$HOME/.aws - Where your AWS creds are stored.
AD_USER: Your Active Directory username. Usually lastname and initial of first name.
AWS_ROLE_ARN: If you know which role to assume, set this.
AWS_DEFAULT_REGION: Default: eu-west-1. Used to find your accessible accounts.
IDP_URL: The NLTP authentication url we use to log in to our federated accounts chooser.
         As the URL changes infrequently, you are unlikely to need this, but its
         provided just in case.
DOCKER_IMAGE: docker image containing the awsaml.py script to run.
EOF
}

# __d(): ... print debug msg to STDERR
__d() {
    [[ ! -z "$DEBUG" ]] && echo >&2 "DEBUG $*"
}

__docker_env_opts() {
    local str=""
    for var in $_USER_OPTS ; do
        if __var_not_empty $var
        then
            __d "... using $var from your environment."
            str="$str -e $var"
        fi
    done
    echo "$str"
}

__var_not_empty() {
    local var_name="$1"
    local var_val="${!var_name}"
    if [[ -z "$var_val" ]]; then
        return 1
    else
        return 0
    fi
}

__prep_env() {
    local img="$1"
    local aws_dir="$2"
    local fn="${FUNCNAME[0]}()"
    local pfn="${FUNCNAME[1]}()"

    __d "... checking docker installed."
    if ! command -v docker >/dev/null
    then
        echo >&2 "ERROR $fn: ... install docker to run."
        return 1
    fi

    # ... check if image is from a remote registry
    if [[ "${img//:*}" =~ \. ]]; then
        __d "... checking docker img $img up to date."
        if ! docker pull $img >/dev/null
        then
            echo "ERROR $fn (from $pfn): ... failed to docker pull"
            return 1
        fi
    fi

    __d "... creating dir $aws_dir unless it already exists"
    mkdir -p $aws_dir

    if [[ ! -d $aws_dir ]]; then
        echo "ERROR $fn (from $pfn): ... could not create directory $aws_dir."
        return 1
    fi

    return 0
}


FROM python:3.7-alpine  

LABEL Name="federated-aws-creds"

CMD ["/awsaml.py"]

RUN \
  apk --no-cache add openssl-dev libffi-dev build-base \
  && pip install --no-cache boto bs4 requests requests-ntlm \
  && apk --no-cache del build-base

COPY awsaml.py /awsaml.py

RUN chmod a+rx /awsaml.py


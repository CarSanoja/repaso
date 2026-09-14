FROM public.ecr.aws/lambda/python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 REPASO_LOCAL_MODE=true REPASO_LOCAL_DATA_DIR=/tmp/repaso-demo
COPY pyproject.toml README.md LICENSE requirements.lock ${LAMBDA_TASK_ROOT}/
COPY src ${LAMBDA_TASK_ROOT}/src
RUN pip install --no-cache-dir setuptools==83.0.0 && pip install --no-build-isolation --no-cache-dir -c requirements.lock .
CMD ["repaso.lambdas.demo.handler"]

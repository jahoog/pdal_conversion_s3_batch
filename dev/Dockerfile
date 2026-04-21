FROM mambaorg/micromamba:latest AS build-image

WORKDIR /app

RUN micromamba install -y -c conda-forge pdal python-pdal numpy boto3 awslambdaric && \
    micromamba clean --all --yes

COPY . .

# Set runtime interface client as default command for the container runtime
ENTRYPOINT [ "/opt/conda/bin/python", "-m", "awslambdaric" ]
# Pass the name of the function handler as an argument to the runtime
CMD [ "lambda_function.handler" ]

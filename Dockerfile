# genairics
# VERSION 0.0.1
# In the dockerfile, dependencies are put that require sudo or are provided by
# modules in our university HPC cluster.
# genairics_dependencies.sh, provides the dependencies that a regular user can install
# genairics_dependencies.sh can also be installed independently from the dockerfile
# by providing the PREFIX env variable

FROM python:3.6.3
ARG buildtype=production
ENV REPOS=/repos
ENV PREFIX=/usr
RUN apt-get update && apt-get install -y git unzip fastqc r-base
RUN Rscript -e 'source("http://bioconductor.org/biocLite.R")' -e 'biocLite(c("limma"))'
RUN mkdir $REPOS
ADD scripts/genairics_dependencies.sh $REPOS/genairics_dependencies.sh
RUN $REPOS/genairics_dependencies.sh
RUN if [ "$buildtype" = "production" ]; then pip install genairics; fi
RUN if [ "$buildtype" = "development" ]; then git clone https://github.com/beukueb/genairics.git && cd genairics && pip install .; fi
ENTRYPOINT ["python","-m","genairics"]
CMD ["-h"]
EXPOSE 8000
VOLUME ["/resources"]
VOLUME ["/data"]
VOLUME ["/results"]

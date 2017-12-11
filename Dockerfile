# genairics
# VERSION 0.0.1

FROM python:3.6.3
RUN apt-get update && apt-get install -y git unzip fastqc r-base
ARG buildtype=production
ENV REPOS=/repos
ENV PREFIX=/usr
RUN mkdir $REPOS
ADD scripts/genairics_dependencies.sh $REPOS/genairics_dependencies.sh
RUN $REPOS/genairics_dependencies.sh
RUN if [ "$buildtype" = "production" ]; then pip install genairics; fi
RUN if [ "$buildtype" = "development" ]; then git clone https://github.com/beukueb/genairics.git && cd genairics && python setup.py install; fi
ENTRYPOINT ["python","-m","genairics"]
CMD ["-h"]
EXPOSE 8000
VOLUME ["/data"]

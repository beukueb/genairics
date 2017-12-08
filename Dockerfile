# genairics
# VERSION 0.0.1

FROM python:3.6.3
#RUN apt-get update && apt-get install -y
RUN scripts/genairics_dependencies.sh
RUN pip install genairics
ENTRYPOINT ["python","-m","genairics"]
CMD ["-h"]
EXPOSE 8000
VOLUME ["/data"]

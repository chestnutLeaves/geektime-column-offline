# 固定基础镜像版本；只复制公开文件，维护目录不进入镜像。
FROM nginx@sha256:0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html about.html course-sources.html /usr/share/nginx/html/
COPY courses/ /usr/share/nginx/html/courses/
COPY articles/ /usr/share/nginx/html/articles/
COPY geektime/ /usr/share/nginx/html/geektime/
COPY relationships/ /usr/share/nginx/html/relationships/
COPY downloads/ /usr/share/nginx/html/downloads/
COPY assets/ /usr/share/nginx/html/assets/
COPY static/ /usr/share/nginx/html/static/
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

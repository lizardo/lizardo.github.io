#!/usr/bin/env python3
import json
import os
import subprocess
import urllib.request
import webbrowser


dockerfile = '''FROM ruby:{ruby}
WORKDIR /usr/src/app
RUN gem install jekyll -v {jekyll}
RUN printf 'source "https://rubygems.org"\\ngem "github-pages", "~> {github-pages}", group: :jekyll_plugins\\n' > Gemfile
RUN bundle update
COPY . .
CMD ["bundle", "exec", "jekyll", "serve", "--host", "0.0.0.0"]'''

def get_versions():
    try:
        return open('.versions.json', 'r')
    except FileNotFoundError:
        with urllib.request.urlopen('https://pages.github.com/versions.json') as f:
            open('.versions.json', 'wb').write(f.read())
        return open('.versions.json', 'r')

project_name = os.path.basename(os.getcwd())

with get_versions() as f:
    versions = json.load(f)

subprocess.run(['docker', 'build', '-t', project_name, '-f', '-', '.'], input=dockerfile.format(**versions).encode('utf-8'), check=True)
p = subprocess.Popen(['docker', 'run', '--rm', '-it', '--name', project_name, '-p', '4000:4000', project_name])
webbrowser.open('http://localhost:4000')
p.communicate()

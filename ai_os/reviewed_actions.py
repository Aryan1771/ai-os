"""Human-reviewed browser and code actions. Never register execute() as a model tool."""
import ipaddress
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
from urllib.parse import urlsplit

from ai_os.config import load_raw_config


def validate(tool, arguments):
    if not isinstance(arguments, dict):
        raise ValueError('Arguments must be an object')
    if tool == 'research_page':
        if set(arguments) != {'url'}:
            raise ValueError('Research requires exactly one URL')
        url = arguments['url']
        if not isinstance(url, str) or len(url) > 2000 or not url.isprintable():
            raise ValueError('Invalid research URL')
        parts = urlsplit(url)
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.port not in (None,443):
            raise ValueError('Only public HTTPS URLs without credentials are supported')
        return arguments
    if tool == 'ask_chatgpt':
        if set(arguments) != {'prompt'} or not isinstance(arguments['prompt'], str) or not 1 <= len(arguments['prompt'].strip()) <= 8000:
            raise ValueError('Provide exactly one prompt of 1–8000 characters')
        return arguments
    if tool == 'write_bash':
        if set(arguments) != {'name', 'source'} or not isinstance(arguments['name'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,60}\.sh', arguments['name']):
            raise ValueError('Use a simple .sh filename, without directories')
        if not isinstance(arguments['source'], str) or not 1 <= len(arguments['source']) <= 16000 or '\0' in arguments['source']:
            raise ValueError('Script must contain 1–16000 characters, without NUL')
        return arguments
    raise ValueError('Unknown reviewed action')


def propose(tool, arguments):
    validate(tool, arguments)
    return {'ok': False, 'error': 'Review this exact action in the native hub.',
            'approval_required': {'tool': tool, 'arguments': arguments}}


def check_bash(source):
    validate('write_bash', {'name':'check.sh', 'source':source})
    result = subprocess.run(['/usr/bin/bash', '--noprofile', '--norc', '-n'], input=source,
                            capture_output=True, text=True, timeout=5, shell=False,
                            env={'PATH':'/usr/bin', 'LANG':'C.UTF-8'})
    return {'ok': result.returncode == 0, 'syntax_only': True, 'error':result.stderr[:4000],
            'message':'Syntax checking does not execute code or establish safety.'}


def public_host(host):
    try:
        addresses = socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(item[4][0]).is_global for item in addresses)
    except (OSError, ValueError):
        return False


def profile_path(home):
    path = home/'data/private/browser-chatgpt'
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def browser_action(tool, arguments, home):
    if not load_raw_config(home)['browser_enabled']:
        raise PermissionError('Enable reviewed browser tools in Permissions first')
    from playwright.sync_api import sync_playwright
    url = arguments.get('url', 'https://chatgpt.com/')
    host = urlsplit(url).hostname
    if not public_host(host):
        raise ValueError('Browser target must resolve only to public addresses')
    # Dedicated AI profile; research gets an empty temporary profile. No personal
    # browser cookies, extensions, traces, screen captures or downloaded files.
    with tempfile.TemporaryDirectory(prefix='regenos-browser-') as directory, sync_playwright() as driver:
        profile = profile_path(home) if tool in {'ask_chatgpt','chatgpt_login'} else Path(directory)
        context = driver.chromium.launch_persistent_context(str(profile), executable_path='/usr/bin/brave',
            headless=tool == 'research_page', chromium_sandbox=True, accept_downloads=False,
            service_workers='block', timeout=15000)
        try:
            context.set_default_timeout(10000)
            if tool != 'chatgpt_login':
                known = {}
                def route(request_route):
                    request = request_route.request
                    parsed = urlsplit(request.url)
                    hostname = parsed.hostname or ''
                    permitted = hostname == host
                    if tool == 'ask_chatgpt':
                        permitted = any(hostname == domain or hostname.endswith('.'+domain)
                                        for domain in ('chatgpt.com','openai.com','oaistatic.com','oaiusercontent.com'))
                    if hostname not in known:
                        known[hostname] = public_host(hostname) if permitted and len(known)<64 else False
                    if parsed.scheme != 'https' or parsed.port not in (None,443) or not permitted or not known[hostname] or request.resource_type in {'media','font'}:
                        request_route.abort()
                    else:
                        request_route.continue_()
                context.route('**/*', route)
            page = context.pages[0] if context.pages else context.new_page()
            response = page.goto(url, wait_until='domcontentloaded', timeout=20000)
            if response is not None and response.status >= 400:
                raise ValueError(f'Website returned HTTP {response.status}; stopped without bypass or retry')
            if tool == 'chatgpt_login':
                import time
                start = time.monotonic()
                while context.pages and time.monotonic()-start < 110:
                    try:
                        context.pages[0].wait_for_timeout(500)
                    except Exception:
                        break
                return {'ok':True,'message':'Browser sign-in window closed. Authentication readiness is checked when sending.'}
            if urlsplit(page.url).hostname != host:
                raise ValueError('Navigation left the approved origin; stopped')
            if tool == 'research_page':
                text = page.locator('body').inner_text(timeout=5000)[:20000]
                if any(marker in text[:3000].lower() for marker in ('verify you are human', 'just a moment...', 'checking your browser')):
                    raise ValueError('Website requires human verification; use the browser manually')
                return {'ok':True,'source':page.url,'text':text,'untrusted_reference':True}
            # Site-specific selectors fail closed if UI/login/CAPTCHA prevents access.
            editor = page.locator('#prompt-textarea')
            editor.wait_for(state='visible',timeout=10000)
            editor.fill(arguments['prompt'])
            send = page.locator('[data-testid="send-button"]')
            send.wait_for(state='visible',timeout=5000)
            if not send.is_enabled():
                raise ValueError('ChatGPT send control unavailable; no prompt submitted')
            if urlsplit(page.url).hostname != 'chatgpt.com':
                raise ValueError('Unexpected page before submission')
            send.click(timeout=5000)
            # No retries: a timeout after clicking may mean submission succeeded.
            reply = page.locator('[data-message-author-role="assistant"]').last
            reply.wait_for(state='visible', timeout=30000)
            return {'ok':True,'source':page.url,'text':reply.inner_text(timeout=5000)[:16000],
                    'message':'Submitted once; response snapshot may still be streaming.', 'untrusted_reference':True}
        finally:
            context.close()


def execute(tool, arguments, home, *, confirmed=False):
    if confirmed is not True:
        raise PermissionError('Exact native confirmation required')
    if tool == 'chatgpt_login':
        if arguments:
            raise ValueError('Login accepts no credentials or arguments')
        return browser_action(tool, arguments, home)
    validate(tool, arguments)
    if tool == 'write_bash':
        result = check_bash(arguments['source'])
        if not result['ok']:
            return result
        target = home/'data/private/drafts'
        target.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise ValueError('Draft directory cannot be a symlink')
        target.chmod(0o700)
        if len(list(target.iterdir())) >= 64:
            raise ValueError('Draft limit reached; review existing drafts first')
        path = target/arguments['name']
        fd = os.open(path, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
        with os.fdopen(fd,'w') as output:
            output.write(arguments['source'])
        return {'ok':True,'path':str(path),'message':'Saved reviewed Bash draft, not executed. Syntax passed; safety is not established.'}
    return browser_action(tool, arguments, home)

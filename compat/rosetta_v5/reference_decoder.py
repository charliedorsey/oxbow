#!/usr/bin/env python3
"""
oxbow.bundle.decode — the NORMATIVE DECODER, transplanted verbatim from the shipped
ROSETTA v0.5.36 self-extracting extractor (the wire's normative decoder per
spec/OXB_WIRE_SPEC.md). Everything above the "generic access layer" marker is
untouched extractor code, including any historically duplicated defs (Python
last-wins reproduces shipped behavior exactly — do NOT tidy). Below the marker:
payload loading (data mode or wrapper), in-memory iteration, doors, tour-track
discovery, and the dual-shape manifest verify ported from the same extractor.
"""
import sys, os, base64, lzma, json, tempfile, shutil
from pathlib import Path


def rv(data,off):
    n=0; sh=0
    while True:
        b=data[off]; off+=1; n|=(b&0x7f)<<sh
        if not b&0x80: return n,off
        sh+=7

def lzd1(b): return lzma.decompress(b,format=lzma.FORMAT_RAW,filters=[{'id':lzma.FILTER_LZMA2,'preset':1}])
def lzd6(b): return lzma.decompress(b,format=lzma.FORMAT_RAW,filters=[{'id':lzma.FILTER_LZMA2,'preset':6}])
def lzd9(b): return lzma.decompress(b,format=lzma.FORMAT_RAW,filters=[{'id':lzma.FILTER_LZMA2,'preset':9}])
def entropy_decode(b): return lzd6(b)

def golden_decode(data):
    if data[:4]!=b'GDN1': raise ValueError('bad golden codec magic')
    pos=4; n,pos=rv(data,pos); parts=[]
    for _ in range(6):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    base_json,lens_s,errs,canon_bits,null_bits,hexbuf=parts
    d=json.loads(base_json.decode('utf-8'))
    entries=[]; lp=hp=0
    for i in range(n):
        ln,lp=rv(lens_s,lp)
        is_null=(null_bits[i//8]>>(i%8))&1
        is_canon=bool((canon_bits[i//8]>>(i%8))&1)
        if is_null:
            hx='NULL'; il=-1
        else:
            bs=hexbuf[hp:hp+ln]; hp+=ln; hx=bs.hex(); il=ln
        entries.append({'input_hex':hx,'input_len':il,'is_canonical':is_canon,'error_code':errs[i]})
    d['entries']=entries
    return json.dumps(d, indent=2).encode('utf-8')






JSON_PUNCT_BYTES=[123,125,91,93,58,44]
def json_token_decode(data):
    if data[:4]!=b'JSN2': raise ValueError('bad JSON token codec magic')
    pos=4; parts=[]
    for _ in range(7):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    sraw,wraw,nraw,ev,raw_s,raw_w,raw_n=parts
    def read_dict(buf):
        arr=[]; p=0; n,p=rv(buf,p)
        for _ in range(n):
            ln,p=rv(buf,p); arr.append(buf[p:p+ln]); p+=ln
        return arr
    sdict=read_dict(sraw); wdict=read_dict(wraw); ndict=read_dict(nraw)
    out=bytearray(); ep=sp=wp=np=0
    while ep<len(ev):
        t=ev[ep]; ep+=1
        if t<6: out.append(JSON_PUNCT_BYTES[t])
        elif t==6: out.extend(b'true')
        elif t==7: out.extend(b'false')
        elif t==8: out.extend(b'null')
        elif t==9: i,ep=rv(ev,ep); out.extend(sdict[i])
        elif t==10: ln,sp=rv(raw_s,sp); out.extend(raw_s[sp:sp+ln]); sp+=ln
        elif t==11: i,ep=rv(ev,ep); out.extend(ndict[i])
        elif t==12: ln,np=rv(raw_n,np); out.extend(raw_n[np:np+ln]); np+=ln
        elif t==13: i,ep=rv(ev,ep); out.extend(wdict[i])
        elif t==14: ln,wp=rv(raw_w,wp); out.extend(raw_w[wp:wp+ln]); wp+=ln
        else: raise ValueError('bad JSON token event')
    return bytes(out)


def json_schema_decode(data):
    if data[:4]!=b'JSN1': raise ValueError('bad JSON schema codec magic')
    pos=4; parts=[]
    for _ in range(4):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    schemas_json, docs_json, raw_offs, raw_concat = parts
    schemas=[tuple(x) for x in json.loads(schemas_json.decode('utf-8'))]
    docs=json.loads(docs_json.decode('utf-8'))
    raw_arr=[]; oo=0; cum=0; offs=[]
    while oo < len(raw_offs):
        d,oo=rv(raw_offs,oo); cum+=d; offs.append(cum)
    for i in range(max(0,len(offs)-1)):
        raw_arr.append(raw_concat[offs[i]:offs[i+1]])
    def inv(x):
        if isinstance(x, list) and x:
            tag=x[0]
            if tag=='@S':
                ks=schemas[x[1]]; vals=x[2]
                return {k:inv(v) for k,v in zip(ks, vals)}
            if tag=='@D': return {k:inv(v) for k,v in x[1]}
            if tag=='@L': return [inv(v) for v in x[1]]
        return x
    out=bytearray()
    for d in docs:
        if d[0]=='@R': out.extend(raw_arr[d[1]])
        elif d[0]=='@J': out.extend(json.dumps(inv(d[1]), indent=2).encode('utf-8'))
        else: raise ValueError('bad JSON doc tag')
    return bytes(out)

JSON_PUNCT_BYTES=[123,125,91,93,58,44]
def json_token_decode(data):
    if data[:4]!=b'JSN2': raise ValueError('bad JSON token codec magic')
    pos=4; parts=[]
    for _ in range(7):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    sraw,wraw,nraw,ev,raw_s,raw_w,raw_n=parts
    def read_dict(buf):
        arr=[]; p=0; n,p=rv(buf,p)
        for _ in range(n):
            ln,p=rv(buf,p); arr.append(buf[p:p+ln]); p+=ln
        return arr
    sdict=read_dict(sraw); wdict=read_dict(wraw); ndict=read_dict(nraw)
    out=bytearray(); ep=sp=wp=np=0
    while ep<len(ev):
        t=ev[ep]; ep+=1
        if t<6: out.append(JSON_PUNCT_BYTES[t])
        elif t==6: out.extend(b'true')
        elif t==7: out.extend(b'false')
        elif t==8: out.extend(b'null')
        elif t==9: i,ep=rv(ev,ep); out.extend(sdict[i])
        elif t==10: ln,sp=rv(raw_s,sp); out.extend(raw_s[sp:sp+ln]); sp+=ln
        elif t==11: i,ep=rv(ev,ep); out.extend(ndict[i])
        elif t==12: ln,np=rv(raw_n,np); out.extend(raw_n[np:np+ln]); np+=ln
        elif t==13: i,ep=rv(ev,ep); out.extend(wdict[i])
        elif t==14: ln,wp=rv(raw_w,wp); out.extend(raw_w[wp:wp+ln]); wp+=ln
        else: raise ValueError('bad JSON token event')
    return bytes(out)


def json_schema_decode(data):
    if data[:4]!=b'JSN1': raise ValueError('bad JSON schema codec magic')
    pos=4; parts=[]
    for _ in range(4):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    schemas_json, docs_json, raw_offs, raw_concat = parts
    schemas=[tuple(x) for x in json.loads(schemas_json.decode('utf-8'))]
    docs=json.loads(docs_json.decode('utf-8'))
    raw_arr=[]; oo=0; cum=0; offs=[]
    while oo < len(raw_offs):
        d,oo=rv(raw_offs,oo); cum+=d; offs.append(cum)
    for i in range(max(0,len(offs)-1)):
        raw_arr.append(raw_concat[offs[i]:offs[i+1]])
    def inv(x):
        if isinstance(x, list) and x:
            tag=x[0]
            if tag=='@S':
                ks=schemas[x[1]]; vals=x[2]
                return {k:inv(v) for k,v in zip(ks, vals)}
            if tag=='@D': return {k:inv(v) for k,v in x[1]}
            if tag=='@L': return [inv(v) for v in x[1]]
        return x
    out=bytearray()
    for d in docs:
        if d[0]=='@R': out.extend(raw_arr[d[1]])
        elif d[0]=='@J': out.extend(json.dumps(inv(d[1]), indent=2).encode('utf-8'))
        else: raise ValueError('bad JSON doc tag')
    return bytes(out)

def markdown_pocket_decode(data):
    if data[:4]!=b'MDF2': raise ValueError('bad MDF2 magic')
    pos=4; np,pos=rv(data,pos); parts=[]
    for _ in range(1 + np + np):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    events=parts[0]; lens=parts[1:1+np]; cont=parts[1+np:]
    lp=[0]*np; cp=[0]*np; out=bytearray()
    for c in events:
        ln,lp[c]=rv(lens[c], lp[c]); out.extend(cont[c][cp[c]:cp[c]+ln]); cp[c]+=ln
    return bytes(out)

JSON_PUNCT_BYTES=[123,125,91,93,58,44]
def json_token_decode(data):
    if data[:4]!=b'JSN2': raise ValueError('bad JSON token codec magic')
    pos=4; parts=[]
    for _ in range(7):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    sraw,wraw,nraw,ev,raw_s,raw_w,raw_n=parts
    def read_dict(buf):
        arr=[]; p=0; n,p=rv(buf,p)
        for _ in range(n):
            ln,p=rv(buf,p); arr.append(buf[p:p+ln]); p+=ln
        return arr
    sdict=read_dict(sraw); wdict=read_dict(wraw); ndict=read_dict(nraw)
    out=bytearray(); ep=sp=wp=np=0
    while ep<len(ev):
        t=ev[ep]; ep+=1
        if t<6: out.append(JSON_PUNCT_BYTES[t])
        elif t==6: out.extend(b'true')
        elif t==7: out.extend(b'false')
        elif t==8: out.extend(b'null')
        elif t==9: i,ep=rv(ev,ep); out.extend(sdict[i])
        elif t==10: ln,sp=rv(raw_s,sp); out.extend(raw_s[sp:sp+ln]); sp+=ln
        elif t==11: i,ep=rv(ev,ep); out.extend(ndict[i])
        elif t==12: ln,np=rv(raw_n,np); out.extend(raw_n[np:np+ln]); np+=ln
        elif t==13: i,ep=rv(ev,ep); out.extend(wdict[i])
        elif t==14: ln,wp=rv(raw_w,wp); out.extend(raw_w[wp:wp+ln]); wp+=ln
        else: raise ValueError('bad JSON token event')
    return bytes(out)


def json_schema_decode(data):
    if data[:4]!=b'JSN1': raise ValueError('bad JSON schema codec magic')
    pos=4; parts=[]
    for _ in range(4):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    schemas_json, docs_json, raw_offs, raw_concat = parts
    schemas=[tuple(x) for x in json.loads(schemas_json.decode('utf-8'))]
    docs=json.loads(docs_json.decode('utf-8'))
    raw_arr=[]; oo=0; cum=0; offs=[]
    while oo < len(raw_offs):
        d,oo=rv(raw_offs,oo); cum+=d; offs.append(cum)
    for i in range(max(0,len(offs)-1)):
        raw_arr.append(raw_concat[offs[i]:offs[i+1]])
    def inv(x):
        if isinstance(x, list) and x:
            tag=x[0]
            if tag=='@S':
                ks=schemas[x[1]]; vals=x[2]
                return {k:inv(v) for k,v in zip(ks, vals)}
            if tag=='@D': return {k:inv(v) for k,v in x[1]}
            if tag=='@L': return [inv(v) for v in x[1]]
        return x
    out=bytearray()
    for d in docs:
        if d[0]=='@R': out.extend(raw_arr[d[1]])
        elif d[0]=='@J': out.extend(json.dumps(inv(d[1]), indent=2).encode('utf-8'))
        else: raise ValueError('bad JSON doc tag')
    return bytes(out)

def markdown_pocket_decode(data):
    if data[:4]!=b'MDF2': raise ValueError('bad MDF2 magic')
    pos=4; np,pos=rv(data,pos); parts=[]
    for _ in range(1 + np + np):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    events=parts[0]; lens=parts[1:1+np]; cont=parts[1+np:]
    lp=[0]*np; cp=[0]*np; out=bytearray()
    for c in events:
        ln,lp[c]=rv(lens[c], lp[c]); out.extend(cont[c][cp[c]:cp[c]+ln]); cp[c]+=ln
    return bytes(out)


def hex_json_decode(data):
    if data[:4]!=b'HXJ1': raise ValueError('bad HXJ1 magic')
    pos=4; parts=[]
    for _ in range(3):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    events, lit, bins=parts
    ep=lp=bp=0; out=bytearray()
    while ep < len(events):
        tag,ep=rv(events,ep); ln,ep=rv(events,ep)
        if tag==0:
            out.extend(lit[lp:lp+ln]); lp += ln
        elif tag==1:
            out.extend(bins[bp:bp+ln].hex().encode('ascii')); bp += ln
        else:
            raise ValueError('bad HXJ1 event')
    return bytes(out)

JSON_PUNCT_BYTES=[123,125,91,93,58,44]
def json_token_decode(data):
    if data[:4]!=b'JSN2': raise ValueError('bad JSON token codec magic')
    pos=4; parts=[]
    for _ in range(7):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    sraw,wraw,nraw,ev,raw_s,raw_w,raw_n=parts
    def read_dict(buf):
        arr=[]; p=0; n,p=rv(buf,p)
        for _ in range(n):
            ln,p=rv(buf,p); arr.append(buf[p:p+ln]); p+=ln
        return arr
    sdict=read_dict(sraw); wdict=read_dict(wraw); ndict=read_dict(nraw)
    out=bytearray(); ep=sp=wp=np=0
    while ep<len(ev):
        t=ev[ep]; ep+=1
        if t<6: out.append(JSON_PUNCT_BYTES[t])
        elif t==6: out.extend(b'true')
        elif t==7: out.extend(b'false')
        elif t==8: out.extend(b'null')
        elif t==9: i,ep=rv(ev,ep); out.extend(sdict[i])
        elif t==10: ln,sp=rv(raw_s,sp); out.extend(raw_s[sp:sp+ln]); sp+=ln
        elif t==11: i,ep=rv(ev,ep); out.extend(ndict[i])
        elif t==12: ln,np=rv(raw_n,np); out.extend(raw_n[np:np+ln]); np+=ln
        elif t==13: i,ep=rv(ev,ep); out.extend(wdict[i])
        elif t==14: ln,wp=rv(raw_w,wp); out.extend(raw_w[wp:wp+ln]); wp+=ln
        else: raise ValueError('bad JSON token event')
    return bytes(out)


def json_schema_decode(data):
    if data[:4]!=b'JSN1': raise ValueError('bad JSON schema codec magic')
    pos=4; parts=[]
    for _ in range(4):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    schemas_json, docs_json, raw_offs, raw_concat = parts
    schemas=[tuple(x) for x in json.loads(schemas_json.decode('utf-8'))]
    docs=json.loads(docs_json.decode('utf-8'))
    raw_arr=[]; oo=0; cum=0; offs=[]
    while oo < len(raw_offs):
        d,oo=rv(raw_offs,oo); cum+=d; offs.append(cum)
    for i in range(max(0,len(offs)-1)):
        raw_arr.append(raw_concat[offs[i]:offs[i+1]])
    def inv(x):
        if isinstance(x, list) and x:
            tag=x[0]
            if tag=='@S':
                ks=schemas[x[1]]; vals=x[2]
                return {k:inv(v) for k,v in zip(ks, vals)}
            if tag=='@D': return {k:inv(v) for k,v in x[1]}
            if tag=='@L': return [inv(v) for v in x[1]]
        return x
    out=bytearray()
    for d in docs:
        if d[0]=='@R': out.extend(raw_arr[d[1]])
        elif d[0]=='@J': out.extend(json.dumps(inv(d[1]), indent=2).encode('utf-8'))
        else: raise ValueError('bad JSON doc tag')
    return bytes(out)

def markdown_pocket_decode(data):
    if data[:4]!=b'MDF2': raise ValueError('bad MDF2 magic')
    pos=4; np,pos=rv(data,pos); parts=[]
    for _ in range(1 + np + np):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    events=parts[0]; lens=parts[1:1+np]; cont=parts[1+np:]
    lp=[0]*np; cp=[0]*np; out=bytearray()
    for c in events:
        ln,lp[c]=rv(lens[c], lp[c]); out.extend(cont[c][cp[c]:cp[c]+ln]); cp[c]+=ln
    return bytes(out)


def hex_json_decode(data):
    if data[:4]!=b'HXJ1': raise ValueError('bad HXJ1 magic')
    pos=4; parts=[]
    for _ in range(3):
        ln,pos=rv(data,pos); parts.append(lzd9(data[pos:pos+ln])); pos+=ln
    events, lit, bins=parts
    ep=lp=bp=0; out=bytearray()
    while ep < len(events):
        tag,ep=rv(events,ep); ln,ep=rv(events,ep)
        if tag==0:
            out.extend(lit[lp:lp+ln]); lp += ln
        elif tag==1:
            out.extend(bins[bp:bp+ln].hex().encode('ascii')); bp += ln
        else:
            raise ValueError('bad HXJ1 event')
    return bytes(out)

def decode_text(wire):
    if wire[:4]==b'RAW1': return lzd1(wire[4:])
    if wire[:4]==b'RAW6': return lzd6(wire[4:])
    if wire[:4]==b'RAW9': return lzd9(wire[4:])
    if wire[:4]==b'GDN1': return golden_decode(wire)
    if wire[:4]==b'JSN1': return json_schema_decode(wire)
    if wire[:4]==b'JSN2': return json_token_decode(wire)
    if wire[:4]==b'MDF2': return markdown_pocket_decode(wire)
    if wire[:4]==b'HXJ1': return hex_json_decode(wire)
    if wire[:4]==b'RAWX': return lzd9(wire[4:])
    if wire[:4]==b'JSN1': return json_schema_decode(wire)
    if wire[:4]==b'JSN2': return json_token_decode(wire)
    if wire[:4]==b'MDF2': return markdown_pocket_decode(wire)
    if wire[:4]==b'HXJ1': return hex_json_decode(wire)
    if wire[:4]==b'RAWX': return lzd9(wire[4:])
    if wire[:4]==b'JSN1': return json_schema_decode(wire)
    if wire[:4]==b'JSN2': return json_token_decode(wire)
    if wire[:4]==b'MDF2': return markdown_pocket_decode(wire)
    if wire[:4]==b'RAWX': return lzd9(wire[4:])
    if wire[:4]==b'JSN1': return json_schema_decode(wire)
    if wire[:4]==b'JSN2': return json_token_decode(wire)
    if wire[:4]!=b'CFP3': raise ValueError('bad text wire')
    def emit_hex(out,bs,upper):
        out.extend(b'0x'); digs=(b'0123456789ABCDEF' if upper else b'0123456789abcdef')
        for by in bs: out.append(digs[(by>>4)&15]); out.append(digs[by&15])
    mode=wire[5]; pos=6
    if mode==1:
        ln,pos=rv(wire,pos); return lzd6(wire[pos:pos+ln])
    corpus=wire[pos]; pos+=1; nrep,pos=rv(wire,pos); nlines,pos=rv(wire,pos)
    streams=[]
    for _ in range(7):
        ln,pos=rv(wire,pos); streams.append(lzd6(wire[pos:pos+ln])); pos+=ln
    dict_s,lens_s,idx_s,sing_s,inter_s,desc_s,cont_s=streams
    offs=[0]; p=0; cur=0
    for _ in range(nrep):
        ln,p=rv(lens_s,p); cur+=ln; offs.append(cur)
    out=bytearray(); ip=sp=dp=cp=0; SINGLE=nrep
    for li in range(nlines):
        ext=(inter_s[li//8]>>(li%8))&1
        if ext and corpus==1:
            d=desc_s[dp]; dp+=1; indent=d>>1; comma=d&1; ln,cp=rv(cont_s,cp)
            out.extend(b' '*indent+b'"'+cont_s[cp:cp+ln]+b'"'); cp+=ln
            if comma: out.append(44)
            out.append(10)
        elif ext and corpus==2:
            b0=desc_s[dp]; n=desc_s[dp+1]; dp+=2; isdec=b0&1; upper=(b0>>1)&1; comma=(b0>>2)&1; indent=b0>>3
            out.extend(b' '*indent)
            for i in range(n):
                bs=cont_s[cp:cp+8]; cp+=8
                if isdec: out.extend(str(int.from_bytes(bs,'big')).encode()+b'ULL')
                else: emit_hex(out,bs,upper); out.extend(b'ULL')
                if i!=n-1: out.extend(b', ')
                elif comma: out.append(44)
            out.append(10)
        else:
            tag,ip=rv(idx_s,ip)
            if tag==SINGLE:
                nl=sing_s.index(b'\n',sp); out.extend(sing_s[sp:nl+1]); sp=nl+1
            else: out.extend(dict_s[offs[tag]:offs[tag+1]])
    return bytes(out)

def gpx_decode(data):
    if data[:4]!=b'GPX2': raise ValueError('bad GPX codec magic')
    off=5; parts=[]
    for _ in range(4):
        ln,off=rv(data,off); parts.append(lzd6(data[off:off+ln])); off+=ln
    meta,events,vals,exact=parts
    mo=0; nt,mo=rv(meta,mo); templ=[]
    for _ in range(nt):
        np,mo=rv(meta,mo); arr=[]
        for _ in range(np):
            ln,mo=rv(meta,mo); arr.append(meta[mo:mo+ln]); mo+=ln
        templ.append(tuple(arr))
    nd,mo=rv(meta,mo); dlines=[]
    for _ in range(nd):
        ln,mo=rv(meta,mo); dlines.append(meta[mo:mo+ln]); mo+=ln
    eo=vo=xo=0; out=bytearray()
    while eo<len(events):
        typ=events[eo]; eo+=1
        if typ==0:
            ln,xo=rv(exact,xo); out.extend(exact[xo:xo+ln]); xo+=ln
        elif typ==1:
            i,eo=rv(events,eo); _,a,b,c=templ[i]
            ln,vo=rv(vals,vo); lat=vals[vo:vo+ln]; vo+=ln
            ln,vo=rv(vals,vo); lon=vals[vo:vo+ln]; vo+=ln
            out.extend(a+lat+b+lon+c)
        elif typ==2:
            i,eo=rv(events,eo); _,a,b=templ[i]
            ln,vo=rv(vals,vo); v=vals[vo:vo+ln]; vo+=ln
            out.extend(a+v+b)
        elif typ==3:
            i,eo=rv(events,eo); out.extend(dlines[i])
        else: raise ValueError('bad gpx event')
    return bytes(out)

def decode_pool(count, offraw, code, decoder):
    if not count: return b'', []
    concat=decoder(code)
    arr=[]; oo=0; cum=0
    for _ in range(count+1):
        d,oo=rv(offraw,oo); cum+=d; arr.append(cum)
    return concat,arr



# ── generic access layer (oxbow additions below this marker) ─────────────────
import hashlib
import re as _re


def load_payload(path):
    """Accept data-mode .oxb (raw RSB1) or a self-extracting wrapper (.rsbin)."""
    b = Path(path).read_bytes()
    if b[:4] == b'RSB1':
        return b
    txt = b.decode('utf-8', errors='ignore')
    m = (_re.search(r"_PAYLOAD_B85\s*=\s*'''(.*?)'''", txt, _re.S)
         or _re.search(r'_PAYLOAD_B85\s*=\s*"""(.*?)"""', txt, _re.S)
         or _re.search(r'_PAYLOAD_B85\s*=\s*"([^"]+)"', txt, _re.S)
         or _re.search(r"_PAYLOAD_B85\s*=\s*'([^']+)'", txt, _re.S))
    if not m:
        raise ValueError('not an RSB1 payload and no _PAYLOAD_B85 found')
    p = base64.b85decode(''.join(m.group(1).split()).encode())
    if p[:4] != b'RSB1':
        p = lzma.decompress(p)
    if p[:4] != b'RSB1':
        raise ValueError('wrapper payload did not decode to RSB1')
    return p


def iter_files(data):
    """Yield (path, blob) for every file in an RSB1 v5 payload — the extractor's
    unpack loop with writes replaced by yields (same traversal, same order)."""
    if data[:4] != b'RSB1' or data[4] != 5:
        raise ValueError('not RSB1 v5')
    pos = 5
    global_pools = []
    global_offsets = []
    for decoder in (decode_text, lzd6, gpx_decode):
        n, pos = rv(data, pos)
        olen, pos = rv(data, pos)
        offraw = lzd6(data[pos:pos + olen]) if olen else b''
        pos += olen
        clen, pos = rv(data, pos)
        code = data[pos:pos + clen]
        pos += clen
        concat, arr = decode_pool(n, offraw, code, decoder)
        global_pools.append(concat)
        global_offsets.append(arr)
    nsec, pos = rv(data, pos)
    for _ in range(nsec):
        ln, pos = rv(data, pos)
        name = data[pos:pos + ln].decode()
        pos += ln
        nt, pos = rv(data, pos)
        nb, pos = rv(data, pos)
        ng, pos = rv(data, pos)
        np_, pos = rv(data, pos)
        plen, pos = rv(data, pos)
        paths_raw = lzd6(data[pos:pos + plen])
        pos += plen
        pools = []
        offsets = []
        for count, decoder in ((nt, decode_text), (nb, lzd6), (ng, gpx_decode)):
            if count:
                olen, pos = rv(data, pos)
                offraw = lzd6(data[pos:pos + olen])
                pos += olen
                clen, pos = rv(data, pos)
                code = data[pos:pos + clen]
                pos += clen
                concat, arr = decode_pool(count, offraw, code, decoder)
                pools.append(concat)
                offsets.append(arr)
            else:
                pools.append(b'')
                offsets.append([])
        po = 0
        for _ in range(np_):
            pool = paths_raw[po]
            po += 1
            l, po = rv(paths_raw, po)
            path = paths_raw[po:po + l].decode()
            po += l
            bi, po = rv(paths_raw, po)
            if pool < 3:
                arr = offsets[pool]
                blob = pools[pool][arr[bi]:arr[bi + 1]]
            else:
                gp = pool - 3
                arr = global_offsets[gp]
                blob = global_pools[gp][arr[bi]:arr[bi + 1]]
            yield path, blob


def unpack_bytes(data, outdir, verbose=True):
    total_files = total_bytes = 0
    for path, blob in iter_files(data):
        fp = Path(outdir) / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(blob)
        total_files += 1
        total_bytes += len(blob)
    if verbose:
        print(f'  total: {total_files} files, {total_bytes:,} bytes', file=sys.stderr)
    return total_files, total_bytes


def info(data):
    if data[:4] != b'RSB1':
        raise ValueError('not RSB1')
    n = by = 0
    for _p, b in iter_files(data):
        n += 1
        by += len(b)
    return {'magic': 'RSB1', 'version': data[4], 'payload_bytes': len(data),
            'files': n, 'raw_bytes': by}


def _manifest_records(m):
    files = m.get('files', [])
    if isinstance(files, list):
        for rec in files:
            if not isinstance(rec, dict) or 'path' not in rec:
                continue
            sha = rec.get('sha256')
            if isinstance(sha, str) and sha.startswith('sha256:'):
                sha = sha.split(':', 1)[1]
            yield rec.get('path'), rec.get('bytes'), sha
    elif isinstance(files, dict):
        for path, val in files.items():
            size = None
            sha = None
            if isinstance(val, str):
                sha = val.split(':', 1)[1] if val.startswith('sha256:') else val
            elif isinstance(val, dict):
                size = val.get('bytes')
                sha = val.get('sha256')
                if isinstance(sha, str) and sha.startswith('sha256:'):
                    sha = sha.split(':', 1)[1]
            yield path, size, sha


MANIFEST_PATHS = ('manifests/MANIFEST.generated.json', 'MANIFEST.generated.json')


def verify_bytes(data):
    """Dual-shape manifest verify (extractor semantics): hash every extracted file,
    compare against the manifest, report counts and mismatches."""
    files = dict(iter_files(data))
    man = None
    for mp in MANIFEST_PATHS:
        if mp in files:
            man = json.loads(files[mp].decode())
            break
    if man is None:
        return {'ok': False, 'error': f'no manifest at {MANIFEST_PATHS}',
                'files': len(files)}
    checked = missing = mismatched = 0
    bad = []
    for path, _size, sha in _manifest_records(man):
        if path is None or sha is None:
            continue
        if path not in files:
            missing += 1
            bad.append(('missing', path))
            continue
        h = hashlib.sha256(files[path]).hexdigest()
        if h != sha:
            mismatched += 1
            bad.append(('sha', path))
        checked += 1
    return {'ok': missing == 0 and mismatched == 0, 'files': len(files),
            'checked': checked, 'missing': missing, 'mismatched': mismatched,
            'bad': bad[:20]}


DOOR_ORDER = ('READ_FIRST.md', 'USER_PATH.md', 'BUNDLE_LAYOUT.md', 'README.md')


def doors(data):
    files = dict(iter_files(data))
    return files, [d for d in DOOR_ORDER if d in files]


def tour_tracks(files):
    """Tours come FROM the bundle (conventions), not from the tool: tours/<track>.md
    or TOUR_<track>.md at root; READ_FIRST.md (etc.) is the default track."""
    tracks = {}
    for p in files:
        if p.startswith('tours/') and p.endswith('.md') and '/' not in p[len('tours/'):]:
            tracks[p[len('tours/'):-3].lower()] = p
        elif '/' not in p and p.startswith('TOUR') and p.endswith('.md'):
            name = p[:-3].replace('TOUR', '').strip('_- ').lower() or 'default'
            tracks[name] = p
    if 'default' not in tracks:
        for d in DOOR_ORDER:
            if d in files:
                tracks['default'] = d
                break
    return tracks

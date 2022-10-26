__all__ = ('MetaRecord', 'MetaMap', 'MetaList')

import os, sys
import datetime, json

class MetaRecord(object):
    COMMENT = None
    def __init__(self, **kwarg):
        if not 'user' in kwarg:
            kwarg['user'] = os.getenv('USERNAME', '=Anonymous=')
            if MetaRecord.COMMENT:
                kwarg['comment'] = MetaRecord.COMMENT
        if not 'when' in kwarg:
            kwarg['when'] = datetime.datetime.now().strftime('%Y-%m-%d')
        self.__dict__.update(kwarg)
    #
    @property
    def metakey(self):
        return (self.when, self.user)
    #
    def __hash__(self):
        return hash(self.metakey)
    #
    def as_jsonable(self):
        res = {}
        for k, v in self.__dict__.items():
            if not k.startswith('_') and isinstance(v, (str, int, float, bool)):
                res[k] = v
        return res
    #
    def __str__(self):
        o = self.as_jsonable()
        who = o.pop('user')
        when = o.pop('when')
        if 'method' in o:
            who = o.pop('method')
        parts = [f'{who} - {when}']
        if 'comment' in o:
            parts.append(o.pop('comment'))
        for k in sorted(o.keys()):
            v = o[k]
            parts.append(f'{k}={v}')
        return ' '.join(parts)
    #

class MetaMap(object):
    def __init__(self, default=None):
        self._default = default if default else MetaRecord()
        #
        self._metamap = {self._default.metakey : self._default}
        self._omap = {}
    #
    @property
    def default(self):
        return self._default
    #
    def addmeta(self, meta, setdefault=False):
        if not meta: meta = MetaRecord()
        comment = meta.comment if hasattr(meta, 'comment') else None
        if not meta.metakey in self._metamap:
            self._metamap[meta.metakey] = meta
        else:
            meta = self._metamap[meta.metakey]
        if setdefault:
            if comment and not hasattr(meta, 'comment'):
                meta.__dict__['comment'] = comment
            self._default = meta
    #
    def addobj(self, obj, meta=None):
        if id(obj) in self._omap and meta is None:
            return
        if meta is None:
            meta = self._default
        self._omap[id(obj)] = meta
    #
    def objmeta(self, obj):
        return self._omap.get(id(obj))
    #
    def itermapping(self, objs):
        mmap = {self.default.metakey : []}
        for obj in objs:
            meta = self._omap.get(id(obj), None)
            if not meta:
                meta = self._default
                self._omap[id(obj)] = meta
            mkey = meta.metakey
            if not mkey in mmap:
                lst = []
                mmap[mkey] = lst
            else:
                lst = mmap[mkey]
            lst.append(obj)
        #
        for mkey in sorted(mmap.keys(), reverse=True):
            lst = mmap[mkey]
            yield self._metamap[mkey], lst
    #

class MetaList(object):
    FWD_LIST_ATTR = ['clear', 'copy', 'count', 'index', 'pop', 'remove', 'reverse', 'sort']
    def __init__(self, *arg, **kwarg):
        if 'meta' in kwarg:
            self._meta = kwarg.pop('meta')
        else:
            self._meta = MetaMap()
        self._lst = list(*arg, **kwarg)
        for obj in self._lst:
            self._meta.addobj(obj)
        #
        self._gray = set()
    #
    @property
    def meta(self):
        return self._meta
    #
    def objmeta(self, item):
        return self._meta.objmeta(item)
    #
    def setGrayMeta(self, metalist):
        self._gray.clear()
        for mrec in metalist:
            if isinstance(mrec, MetaRecord):
                mrec = mrec.metakey
            self._gray.add(mrec)
    #
    def isGrayMetaRec(self, mrec):
        if isinstance(mrec, MetaRecord):
            mrec = mrec.metakey
        return mrec in self._gray
    #
    def isGray(self, item):
        mr = self.objmeta(item)
        return mr.metakey in self._gray
    #
    def __getattribute__(self, item):
        if item in MetaList.FWD_LIST_ATTR:
            return self._lst.__getattribute__(item)
        return super(MetaList, self).__getattribute__(item)
    #
    def append(self, x):
        self._lst.append(x)
        self._meta.addobj(x)
    #
    def extend(self, iterable):
        for x in iterable:
            self._lst.append(x)
            self._meta.addobj(x)
    #
    def update(self, iterable):
        self._lst.clear()
        self.extend(iterable)
    #
    def insert(self, i, x):
        self._lst.insert(i, x)
        self._meta.addobj(x)
    #
    def itermapping(self):
        return self._meta.itermapping(self._lst)
    #
    def __str__(self):
        return self._lst.__str__()
    def __repr__(self):
        return self._lst.__repr__()
    def __len__(self):
        return self._lst.__len__()
    def __getitem__(self, key):
        return self._lst.__getitem__(key)
    def __setitem__(self, key, value):
        self._lst.__setitem__(key, value)
        self._meta.addobj(value)
    def __delitem__(self, key):
        return self._lst.__delitem__(key)
    def __iter__(self):
        return self._lst.__iter__()
    def __reversed__(self):
        return self._lst.__reversed__()
    def __contains__(self, item):
        return self._lst.__contains__(item)
    #

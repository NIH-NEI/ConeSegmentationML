__all__ = ('MetaRecord', 'MetaMap', 'MetaList', 'metainit',)

import os, sys
import datetime, json

def metainit():
    MetaRecord.TODAY = datetime.datetime.now().strftime('%Y-%m-%d')

class MetaRecord(object):
    CURRENT_USER = os.getenv('USERNAME', os.getenv('USER', '=Anonymous='))
    TODAY = None
    COMMENT = None
    REAL_USER = None
    def __init__(self, **kwarg):
        self._id = 1
        if not 'user' in kwarg:
            kwarg['user'] = MetaRecord.CURRENT_USER
        if not 'when' in kwarg:
            kwarg['when'] = MetaRecord.TODAY
        if not 'realUser' in kwarg and MetaRecord.REAL_USER and \
                kwarg['user'] == MetaRecord.CURRENT_USER and kwarg['when'] == MetaRecord.TODAY:
            kwarg['realUser'] = MetaRecord.REAL_USER
        self.__dict__.update(kwarg)
    #
    @classmethod
    def current_key(cls):
        return (cls.TODAY, cls.CURRENT_USER)
    #
    @property
    def metakey(self):
        return (self.when, self.user, self._id)
    @property
    def userkey(self):
        return (self.when, self.user)
    #
    @property
    def who(self):
        if hasattr(self, 'method'):
            return self.method
        return self.user
    #
    @property
    def realWho(self):
        if hasattr(self, 'method'):
            return self.method
        if hasattr(self, 'realUser'):
            return self.realUser
        return self.user
    #
    @realWho.setter
    def realWho(self, v):
        if not v or self.who == v:
            if 'realUser' in self.__dict__:
                del self.__dict__['realUser']
        else:
            self.__dict__['realUser'] = v
    #
    @property
    def description(self):
        parts = []
        o = self.as_jsonable()
        for attr in ('user', 'when', 'method', 'realUser'):
            if attr in o:
                del o[attr]
        if 'comment' in o:
            parts.append(o.pop('comment'))
        for k in sorted(o.keys()):
            v = o[k]
            parts.append(f'{k}={v}')
        return ' '.join(parts)
    #
    def __hash__(self):
        return hash(self.metakey)
    #
    def as_jsonable(self):
        res = {}
        if MetaRecord.COMMENT and self.userkey == self.current_key():
            res['comment'] = MetaRecord.COMMENT
        for k, v in self.__dict__.items():
            if not k.startswith('_') and isinstance(v, (str, int, float, bool)):
                res[k] = v
        return res
    #
    def copy(self):
        return MetaRecord(**self.as_jsonable())
    #
    def __str__(self):
        return f'{self.realWho} - {self.when} {self.description}'
    #

class MetaMap(object):
    def __init__(self, default=None):
        self._next_id = 1
        self._default = default.copy() if default else MetaRecord()
        self._default._id = self._next_id
        self._next_id += 1
        #
        self._metamap = {self._default.metakey : self._default}
        self._omap = {}
    #
    @property
    def default(self):
        return self._default
    @default.setter
    def default(self, v):
        if isinstance(v, MetaRecord):
            v = v.metakey
        elif not isinstance(v, tuple):
            return
        if v in self._metamap:
            self._default = self._metamap[v]
    #
    def _last_userkey(self, meta):
        res = None
        for _meta in self._metamap.values():
            if _meta.userkey == meta.userkey:
                if res is None or res._id < _meta._id:
                    res = _meta
        return res
    def addmeta(self, meta, setdefault=False, newid=False):
        if not meta: meta = MetaRecord()
        else: meta = meta.copy()
        comment = meta.comment if hasattr(meta, 'comment') else None
        _meta = None if newid else self._last_userkey(meta)
        if _meta is None:
            meta._id = self._next_id
            self._next_id += 1
            self._metamap[meta.metakey] = meta
        else:
            meta = _meta
        if setdefault:
            if comment and not hasattr(meta, 'comment'):
                meta.__dict__['comment'] = comment
            self._default = meta
        return meta
    #
    def can_delete_meta(self, mkey):
        if isinstance(mkey, MetaRecord):
            mkey = mkey.metakey
        elif not isinstance(mkey, tuple):
            return False
        if not mkey in self._metamap:
            return False
        mrec = self._metamap[mkey]
        if mrec.userkey != MetaRecord.current_key():
            return False
        for _mrec in self._omap.values():
            if _mrec is mrec:
                return False
        for _mrec in self._metamap.values():
            if _mrec.userkey == mrec.userkey and _mrec.metakey != mrec.metakey:
                return True
        return False
    #
    def delmeta(self, mkey):
        if not self.can_delete_meta(mkey):
            return False
        if isinstance(mkey, MetaRecord):
            mkey = mkey.metakey
        mrec = self._metamap.pop(mkey)
        if mrec is self._default:
            self._default = self._last_userkey(mrec)
        return True
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
        for mkey, mrec in self._metamap.items():
            if not mkey in mmap and mrec.userkey == MetaRecord.current_key():
                mmap[mkey] = []
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
    def canDeleteMetaRec(self, mrec):
        return self._meta.can_delete_meta(mrec)
    #
    def deleteMetaRec(self, mrec):
        return self._meta.delmeta(mrec)
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

metainit()

import unittest
import os
from rdbtools.parser import RdbCallback, RdbParser

class RedisParserTestCase(unittest.TestCase):
    def setUp(self):
        pass
        
    def tearDown(self):
        pass
    
    def load_rdb(self, file_name) :
        r = MockRedis()
        parser = RdbParser(r)
        parser.parse(os.path.join(os.path.dirname(__file__), 'dumps', file_name))
        return r

    def test_empty_rdb(self):
        r = self.load_rdb('empty_database.rdb')
        self.assert_('start_rdb' in r.methods_called)
        self.assert_('end_rdb' in r.methods_called)
        self.assertEquals(len(r.databases), 0, msg = "didn't expect any databases")

    def test_keys_with_expiry(self):
        self.fail("Not Implemented")
    
    def test_integer_keys(self):
        r = self.load_rdb('integer_keys.rdb')
        self.assertEquals(r.databases[0][125], "Positive 8 bit integer")
        self.assertEquals(r.databases[0][0xABAB], "Positive 16 bit integer")
        self.assertEquals(r.databases[0][0x0AEDD325], "Positive 32 bit integer")
        
    def test_negative_integer_keys(self):
        r = self.load_rdb('integer_keys.rdb')
        self.assertEquals(r.databases[0][-123], "Negative 8 bit integer")
        self.assertEquals(r.databases[0][-0x7325], "Negative 16 bit integer")
        self.assertEquals(r.databases[0][-0x0AEDD325], "Negative 32 bit integer")
    
    def test_string_key_with_compression(self):
        r = self.load_rdb('easily_compressible_string_key.rdb')
        key = "".join('a' for x in range(0, 200))
        value = "Key that redis should compress easily"
        self.assertEquals(r.databases[0][key], value)

    def test_zipmap_thats_compresses_easily(self):
        r = self.load_rdb('zipmap_that_compresses_easily.rdb')
        self.assertEquals(r.databases[0]["zipmap_compresses_easily"]["a"], "aa")
        self.assertEquals(r.databases[0]["zipmap_compresses_easily"]["aa"], "aaaa")
        self.assertEquals(r.databases[0]["zipmap_compresses_easily"]["aaaaa"], "aaaaaaaaaaaaaa")
        
    def test_zipmap_that_doesnt_compress(self):
        r = self.load_rdb('zipmap_that_doesnt_compress.rdb')
        self.assertEquals(r.databases[0]["zimap_doesnt_compress"]["MKD1G6"], "2")
        self.assertEquals(r.databases[0]["zimap_doesnt_compress"]["YNNXK"], "F7TI")

    def test_dictionary(self):
        r = self.load_rdb('dictionary.rdb')
        self.assertEquals(r.lengths[0]["force_dictionary"], 1000)
        self.assertEquals(r.databases[0]["force_dictionary"]["ZMU5WEJDG7KU89AOG5LJT6K7HMNB3DEI43M6EYTJ83VRJ6XNXQ"], 
                    "T63SOS8DQJF0Q0VJEZ0D1IQFCYTIPSBOUIAI9SB0OV57MQR1FI")
        self.assertEquals(r.databases[0]["force_dictionary"]["UHS5ESW4HLK8XOGTM39IK1SJEUGVV9WOPK6JYA5QBZSJU84491"], 
                    "6VULTCV52FXJ8MGVSFTZVAGK2JXZMGQ5F8OVJI0X6GEDDR27RZ")
    
    def test_ziplist_that_compresses_easily(self):
        r = self.load_rdb('ziplist_that_compresses_easily.rdb')
        self.assertEquals(r.lengths[0]["ziplist_compresses_easily"], 6)
        for length in (6, 12, 18, 24, 30, 36) :
            self.assert_(("".join("a" for x in xrange(length))) in r.databases[0]["ziplist_compresses_easily"])
    
    def test_ziplist_that_doesnt_compress(self):
        r = self.load_rdb('ziplist_that_doesnt_compress.rdb')
        self.assertEquals(r.lengths[0]["ziplist_doesnt_compress"], 2)
        self.assert_("aj2410" in r.databases[0]["ziplist_doesnt_compress"])
        self.assert_("cc953a17a8e096e76a44169ad3f9ac87c5f8248a403274416179aa9fbd852344" 
                        in r.databases[0]["ziplist_doesnt_compress"])
    
    def test_ziplist_with_integers(self):
        r = self.load_rdb('ziplist_with_integers.rdb')
        self.assert_(63 in r.databases[0]["ziplist_with_integers"])
        self.assert_(16380 in r.databases[0]["ziplist_with_integers"])
        self.assert_(65535 in r.databases[0]["ziplist_with_integers"])
        self.assert_(0x7fffffffffffffff in r.databases[0]["ziplist_with_integers"])
        
class MockRedis(RdbCallback):
    def __init__(self) :
        self.databases = {}
        self.lengths = {}
        self.expiry = {}
        self.methods_called = []
        self.dbnum = 0

    def currentdb(self) :
        return self.databases[self.dbnum]
    
    def store_expiry(self, key, expiry) :
        self.expiry[self.dbnum][key] = expiry
    
    def store_length(self, key, length) :
        if not self.dbnum in self.lengths :
            self.lengths[self.dbnum] = {}
        self.lengths[self.dbnum][key] = length

    def get_length(self, key) :
        if not key in self.lengths[self.dbnum] :
            raise Exception('Key %s does not have a length' % key)
        return self.lengths[self.dbnum][key]
        
    def start_rdb(self):
        self.methods_called.append('start_rdb')
    
    def start_database(self, dbnum):
        self.dbnum = dbnum
        self.databases[dbnum] = {}
        self.expiry[dbnum] = {}
        self.lengths[dbnum] = {}
    
    def set(self, key, value, expiry):
        self.currentdb()[key] = value
        if expiry :
            self.store_expiry(key, expiry)
    
    def start_hash(self, key, length, expiry):
        if key in self.currentdb() :
            raise Exception('start_hash called with key %s that already exists' % key)
        else :
            self.currentdb()[key] = {}
        if expiry :
            self.store_expiry(key, expiry)
        self.store_length(key, length)
    
    def hset(self, key, field, value):
        if not key in self.currentdb() :
            raise Exception('start_hash not called for key = %s', key)
        self.currentdb()[key][field] = value
    
    def end_hash(self, key):
        if not key in self.currentdb() :
            raise Exception('start_hash not called for key = %s', key)
        if len(self.currentdb()[key]) != self.lengths[self.dbnum][key] :
            raise Exception('Lengths mismatch on hash %s, expected length = %d, actual = %d'
                                 % (key, self.lengths[self.dbnum][key], len(currentdb()[key])))
    
    def start_set(self, key, cardinality, expiry):
        if key in self.currentdb() :
            raise Exception('start_set called with key %s that already exists' % key)
        else :
            self.currentdb()[key] = []
        if expiry :
            self.store_expiry(key, expiry)
        self.store_length(key, length)

    def sadd(self, key, member):
        if not key in self.currentdb() :
            raise Exception('start_set not called for key = %s', key)
        self.currentdb()[key].append(value)
    
    def end_set(self, key):
        if not key in self.currentdb() :
            raise Exception('start_set not called for key = %s', key)
        if len(self.currentdb()[key]) != self.lengths[self.dbnum][key] :
            raise Exception('Lengths mismatch on set %s, expected length = %d, actual = %d'
                                 % (key, self.lengths[self.dbnum][key], len(currentdb()[key])))

    def start_list(self, key, length, expiry):
        if key in self.currentdb() :
            raise Exception('start_list called with key %s that already exists' % key)
        else :
            self.currentdb()[key] = []
        if expiry :
            self.store_expiry(key, expiry)
        self.store_length(key, length)
    
    def rpush(self, key, value) :
        if not key in self.currentdb() :
            raise Exception('start_list not called for key = %s', key)
        self.currentdb()[key].append(value)
    
    def end_list(self, key):
        if not key in self.currentdb() :
            raise Exception('start_set not called for key = %s', key)
        if len(self.currentdb()[key]) != self.lengths[self.dbnum][key] :
            raise Exception('Lengths mismatch on list %s, expected length = %d, actual = %d'
                                 % (key, self.lengths[self.dbnum][key], len(currentdb()[key])))

    def start_sorted_set(self, key, length, expiry):
        if key in self.currentdb() :
            raise Exception('start_sorted_set called with key %s that already exists' % key)
        else :
            self.currentdb()[key] = []
        if expiry :
            self.store_expiry(key, expiry)
        self.store_length(key, length)
    
    def zadd(self, key, score, member):
        if not key in self.currentdb() :
            raise Exception('start_sorted_set not called for key = %s', key)
        self.currentdb()[key][member] = score
    
    def end_sorted_set(self, key):
        if not key in self.currentdb() :
            raise Exception('start_set not called for key = %s', key)
        if len(self.currentdb()[key]) != self.lengths[self.dbnum][key] :
            raise Exception('Lengths mismatch on sortedset %s, expected length = %d, actual = %d'
                                 % (key, self.lengths[self.dbnum][key], len(currentdb()[key])))

    def end_database(self, dbnum):
        if self.dbnum != dbnum :
            raise Exception('start_database called with %d, but end_database called %d instead' % (self.dbnum, dbnum))
    
    def end_rdb(self):
        self.methods_called.append('end_rdb')


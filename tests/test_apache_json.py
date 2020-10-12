# -*- coding: utf-8 -*-
from __future__ import absolute_import

import json
import time
from multiprocessing import Process

import pytest
import six

import thriftpy2
from thriftpy2.http import make_server as make_http_server, \
    make_client as make_http_client
from thriftpy2.protocol import TApacheJSONProtocolFactory
from thriftpy2.rpc import make_server as make_rpc_server, \
    make_client as make_rpc_client
from thriftpy2.thrift import TProcessor
from thriftpy2.transport import TMemoryBuffer
from thriftpy2.transport.buffered import TBufferedTransportFactory


def recursive_vars(obj):
    if isinstance(obj, six.string_types):
        return six.ensure_str(obj)
    if isinstance(obj, six.binary_type):
        return six.ensure_binary(obj)
    if isinstance(obj, (int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: recursive_vars(v) for k, v in obj.items()}
    if isinstance(obj, (list, set)):
        return [recursive_vars(v) for v in obj]
    if hasattr(obj, '__dict__'):
        return recursive_vars(vars(obj))


def test_thrift_transport():
    test_thrift = thriftpy2.load(
        "apache_json_test.thrift",
        module_name="test_thrift"
    )
    Test = test_thrift.Test
    Foo = test_thrift.Foo
    test_object = Test(
        tbool=False,
        tbyte=16,
        tdouble=1.234567,
        tlong=123123123,
        tshort=123,
        tint=12345678,
        tstr="Testing String",
        tsetofints={1, 2, 3, 4, 5},
        tmap_of_int2str={
            1: "one",
            2: "two",
            3: "three"
        },
        tlist_of_strings=["how", "do", "i", "test", "this?"],
        tmap_of_str2foo={'first': Foo("first"), "2nd": Foo("baz")},
        tmap_of_str2foolist={
            'test': [Foo("test list entry")]
        },
        tmap_of_str2mapofstring2foo={
            "first": {
                "second": Foo("testing")
            }
        },
        tmap_of_str2stringlist={
            "words": ["dog", "cat", "pie"],
            "other": ["test", "foo", "bar", "baz", "quux"]
        },
        tfoo=Foo("test food"),
        tlist_of_foo=[Foo("1"), Foo("2"), Foo("3")],
        tlist_of_maps2int=[
            {"one": 1, "two": 2, "three": 3}
        ],
        tmap_of_int2foo={
            1: Foo("One"),
            2: Foo("Two"),
            5: Foo("Five")
        },
        tbinary=b"\x01\x0fabc123\x00\x02"
    )
    # A request generated by apache thrift that matches the above object
    request_data = b"""[1,"test",1,0,{"1":{"rec":{"1":{"tf":0},"2":{"i8":16},
    "3":{"i16":123},"4":{"i32":12345678},"5":{"i64":123123123},"6":
    {"dbl":1.234567},"7":{"str":"Testing String"},"8":{"lst":["str",5,
    "how","do","i","test","this?"]},"9":{"map":["i32","str",3,{"1":"one",
    "2":"two","3":"three"}]},"10":{"set":["i32",5,1,2,3,4,5]},
    "11":{"map":["str","rec",2,{"first":{"1":{"str":"first"}},"2nd":
    {"1":{"str":"baz"}}}]},"12":{"map":["str","lst",
    2,{"words":["str",3,"dog","cat","pie"],"other":["str",5,"test",
    "foo","bar","baz","quux"]}]},"13":{"map":["str",
    "map",1,{"first":["str","rec",1,{"second":{"1":{"str":"testing"}}}]}]},
    "14":{"lst":["rec",3,{"1":{"str":"1"}},
    {"1":{"str":"2"}},{"1":{"str":"3"}}]},"15":{"rec":{"1":{
    "str":"test food"}}},"16":{"lst":["map",1,["str","i32",
    3,{"one":1,"two":2,"three":3}]]},"17":{"map":["str","lst",1,{"test":
    ["rec",1,{"1":{"str":"test list entry"}}]}]},
    "18":{"map":["i32","rec",3,{"1":{"1":{"str":"One"}},"2":{"1":
    {"str":"Two"}},"5":{"1":{"str":"Five"}}}]},
    "19":{"str":"AQ9hYmMxMjMAAg=="}}}}]"""

    class Handler:
        @staticmethod
        def test(t):
            # t should match the object above
            assert recursive_vars(t) == recursive_vars(test_object)
            return t

    tp2_thrift_processor = TProcessor(test_thrift.TestService, Handler())
    tp2_factory = TApacheJSONProtocolFactory()
    iprot = tp2_factory.get_protocol(TMemoryBuffer(request_data))
    obuf = TMemoryBuffer()
    oprot = tp2_factory.get_protocol(obuf)

    tp2_thrift_processor.process(iprot, oprot)

    # output buffers should be the same
    final_data = obuf.getvalue()
    assert json.loads(request_data.decode('utf8'))[4]['1'] == \
           json.loads(final_data.decode('utf8'))[4]['0']


@pytest.mark.parametrize('server_func', [(make_rpc_server, make_rpc_client),
                                         (make_http_server, make_http_client)])
def test_client(server_func):
    test_thrift = thriftpy2.load(
        "apache_json_test.thrift",
        module_name="test_thrift"
    )

    class Handler:
        @staticmethod
        def test(t):
            return t

    def run_server():
        server = make_http_server(
            test_thrift.TestService,
            handler=Handler(),
            host='localhost',
            port=9090,
            proto_factory=TApacheJSONProtocolFactory(),
            trans_factory=TBufferedTransportFactory()
        )
        server.serve()

    proc = Process(target=run_server, )
    proc.start()
    time.sleep(0.25)

    try:
        test_object = test_thrift.Test(
            tdouble=12.3456,
            tint=567,
            tstr='A test \'{["string',
            tmap_of_bool2str={True: "true string", False: "false string"},
            tmap_of_bool2int={True: 0, False: 1}
        )

        client = make_http_client(
            test_thrift.TestService,
            host='localhost',
            port=9090,
            proto_factory=TApacheJSONProtocolFactory(),
            trans_factory=TBufferedTransportFactory()
        )
        res = client.test(test_object)
        assert recursive_vars(res) == recursive_vars(test_object)
    finally:
        proc.terminate()
    time.sleep(1)
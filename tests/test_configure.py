import asyncio
from unittest.mock import Mock
import warnings

import pytest

from aiotraversal.app import Application
from aiotraversal.app import _ConfigureIncluderWrapper


def test_include__func(loop, app):
    func = Mock(name='func')

    with app.configure(loop=loop) as config:
        config.include(func)

    assert func.call_count == 1
    assert len(func.call_args[0]) == 1

    wrapper = func.call_args[0][0]
    assert isinstance(wrapper, _ConfigureIncluderWrapper)
    assert wrapper._include_object is config
    assert wrapper._include_module == func.__module__


def test_include__str_includeme(loop, app):
    with app.configure(loop=loop) as config:
        config.include('tests.for_include')
        name, wrapper = config['test_include_info']

    assert name == 'includeme'
    assert isinstance(wrapper, _ConfigureIncluderWrapper)


def test_include__str_func(loop, app):
    with app.configure(loop=loop) as config:
        config.include('tests.for_include.func')
        name, wrapper = config['test_include_info']

    assert name == 'func'
    assert isinstance(wrapper, _ConfigureIncluderWrapper)


def test_include__str_not_callable(loop, app):
    with app.configure(loop=loop) as config:
        with pytest.raises(TypeError):
            config.include('tests.for_include.not_callable')


def test_include__str_error(loop, app):
    with app.configure(loop=loop) as config:
        with pytest.raises(ImportError):
            config.include('tests.for_include.not_exists')


def test_include__str_error_includeme(loop, app):
    with app.configure(loop=loop) as config:
        with pytest.raises(ImportError):
            config.include('tests.for_include.helpers')


def test_include__deeper(loop, app):
    with app.configure(loop=loop) as config:
        config.include('tests.for_include')
        name, wrapper = config['test_include_info']
        assert name == 'includeme'
        assert isinstance(wrapper, _ConfigureIncluderWrapper)

        wrapper.include('.func')
        name, wrapper = wrapper['test_include_info']
        assert name == 'func'
        assert isinstance(wrapper, _ConfigureIncluderWrapper)


def test_include_deferred(loop, app):
    def func(config, parent):
        config['deferred'] = True
        assert config is not parent

    with app.configure(loop=loop) as config:
        assert 'deferred' not in config
        assert 'deferred' not in app
        config.include_deferred(func, parent=config)
        assert 'deferred' not in config
        assert 'deferred' not in app

    assert 'deferred' in app


def test_include_deferred__deeper(loop, app):
    def func_deferr(config, parent):
        config['deferred'] = True

    def func(config, parent):
        config.include_deferred(func_deferr, parent=config)

    with app.configure(loop=loop) as config:
        config.include(func, parent=config)
        assert 'deferred' not in config
        assert 'deferred' not in app

    assert 'deferred' in app


def test_add_method(loop, app):
    def func(app, *args, **kwargs):
        return (app, args, kwargs)

    with app.configure(loop=loop) as config:
        config.add_method('meth', func)
        assert config.meth(1, b=2) == (config, (1,), {'b': 2})


def test_add_method__twice(loop, app):
    def func_1(app):
        return 1

    def func_2(app):
        return 2

    with app.configure(loop=loop) as config:
        config.add_method('meth', func_1)

        with warnings.catch_warnings(record=True) as w:
            config.add_method('meth', func_2)
            assert len(w) == 1

        assert config.meth() == 2


def test_bind_view__resource(loop, app):
    class Res:
        pass

    def view(request, resource, tail):
        return 'response'

    with app.configure(loop=loop) as config:
        config.bind_view(Res, view)

    assert Res in app.router.resources


def test_bind_view__exception(loop, app):
    class Exc(Exception):
        pass

    def view(request, exc):
        return 'response'

    with app.configure(loop=loop) as config:
        config.bind_view(Exc, view)

    assert Exc in app['exc_handlers']


def test_bind_view__exception_w_tail(loop, app):
    class Exc(Exception):
        pass

    def view(request, exc):
        return 'response'

    with app.configure(loop=loop) as config:
        with pytest.raises(TypeError):
            config.bind_view(Exc, view, '/a/b/c')


def test_cleanup(loop, app):
    result = []

    @asyncio.coroutine
    def first(r):
        r.append(1)
        yield from asyncio.sleep(0)

    def second(app):
        result.append(2)
        assert isinstance(app, Application)

    @asyncio.coroutine
    def third(app):
        result.append(3)
        assert isinstance(app, Application)
        yield from asyncio.sleep(0)

    with app.configure(loop=loop) as config:
        assert isinstance(config.on_cleanup, list)
        assert not result
        config.on_cleanup.append(first(result))
        config.on_cleanup.append(second)
        config.on_cleanup.append(third)
        assert not result

    assert not result
    loop.run_until_complete(app.cleanup())
    assert result == [1, 2, 3]

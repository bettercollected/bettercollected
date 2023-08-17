Documentation
=============

--------------

**This project was generated with:** `fastapi-mvc <https://github.com/fastapi-mvc/fastapi-mvc>`__

--------------

Quickstart
~~~~~~~~~~

If You want to go easy way and use provided virtualized environment You'll need to have installed:

* rsync
* Vagrant `(How to install vagrant) <https://www.vagrantup.com/downloads>`__
* (Optional) Enabled virtualization in BIOS

First run ``vagrant up`` in project root directory and enter virtualized environment using ``vagrant ssh``
Then run following commands to bootstrap local development cluster exposing ``fastapi-mvc`` application.

.. code-block:: bash

    cd /syncd
    make dev-env

.. note::
    This process may take a while on first run.

Once development cluster is up and running you should see summary listing application address:

.. code-block:: bash

    Kubernetes cluster ready

    fastapi-mvc available under: http://auth.192.168.49.2.nip.io/

    You can delete dev-env by issuing: minikube delete

.. note::
    Above address may be different for your installation.

    Provided virtualized env doesn't have port forwarding configured which means, that bootstrapped application stack in k8s won't be accessible on Host OS.

Deployed application stack in Kubernetes:

.. code-block:: bash

    vagrant@ubuntu-focal:/syncd$ make dev-env
    ...
    ...
    ...
    Kubernetes cluster ready
    FastAPI available under: http://auth.192.168.49.2.nip.io/
    You can delete dev-env by issuing: make clean
    vagrant@ubuntu-focal:/syncd$ kubectl get all -n auth
    NAME                        READY   STATUS    RESTARTS   AGE
    pod/auth-649966bb7f-r694l   1/1     Running   0          114s

    NAME           TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)    AGE
    service/auth   ClusterIP   10.97.16.46   <none>        8000/TCP   114s

    NAME                   READY   UP-TO-DATE   AVAILABLE   AGE
    deployment.apps/auth   1/1     1            1           114s

    NAME                              DESIRED   CURRENT   READY   AGE
    replicaset.apps/auth-649966bb7f   1         1         1       114s
    vagrant@ubuntu-focal:/syncd$ curl http://auth.192.168.49.2.nip.io/api/ready
    {"status":"ok"}
Documentation
-------------

This part of the documentation guides you through all of the features and usage.

.. toctree::
   :maxdepth: 2

   install
   
   usage
   deployment

API Reference
-------------

If you are looking for information on a specific function, class, or
method, this part of the documentation is for you.

.. toctree::
   :maxdepth: 2

   api

Miscellaneous Pages
-------------------

.. toctree::
   :maxdepth: 2

   license
   changelog

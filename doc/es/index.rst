==========
Prestashop
==========

La comunicación entre el ERP y Prestashop se ha dividido en diferentes módulos según
las necesidades de conexión que necesiten. La base de la integración con Prestashop
le permite configurar los servidores de Prestashop y la importación/exportación de
pedidos de venta (con la generación de productos, clientes y direcciones).

Para más funcionalidades para la integración con Prestashop dispone de más módulos como:

* prestashop_product: sincronización de productos
* prestashop_stock: sincronización de stock

La comunicación entre Prestashop y el ERP se realiza mediante los webservices de
Prestashop (API).

---------------------------------
Activar Webservices de Prestashop
---------------------------------

Si usamos Apache, instalaremos el php5-curl

    sudo apt-get install php5-curl

URL's amigables
---------------

A nivel de servidor deberemos activar el ModRewrite

    sudo a2enmod rewrite
    sudo service apache2 restart

Nos aseguramos que en la configuración de nuestro site-available disponemos de:

    AllowOverride All

A Prestashop, en Preferencias y SEO, debemos activar la opción en "URL configuración"
la opción "URL amigable". Cuando lo guardamos, nos regenerá de nuevo un nuevo fichero
.htaccess

Crear una key webservices
-------------------------

En "Parámetros Avanzados/Servicios Web" activaremos la opción "Webservices" y añadiremos
una clave. Esta clave marcaremos los servicios que puede gestionar.

Para acceder a la API podemos desdel navegador acceder con nuestra clave:

    http://UCCLLQ9N2ARSHWCXLT74KUKSSK34BFKX@example.com/prestasshop/api/

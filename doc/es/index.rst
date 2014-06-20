==========
Prestashop
==========

A diferencia del módulo Prestashop Connect de OpenERP, este módulo
se ha simplificado y dividido en dos: pedidos de venta y productos.
De esta forma, puede instalar el módulo de Prestashop para ventas sin necesidad de
gestionar los productos de Prestashop con el ERP.

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

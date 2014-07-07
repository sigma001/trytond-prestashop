==========
Prestashop
==========

.. inheritref:: prestashop/prestashop:section:pedidos

Pedidos
=======

La importación de pedidos de Prestashop a Tryton se puede hacer de dos formas:

* **Importación manual**: A |menu_sale_shop| dispone del botón **Importar
  pedidos**.
* **Importación automática**: En la configuración de la tienda active el
  campo **Planificador de tareas**. Importa los pedidos según el intervalo de
  ejecución del cron (cada 30 minutos, 20 minutos,...)

.. inheritref:: prestashop/prestashop:section:importar_pedidos

Importar pedidos
================

En el menú |menu_sale_shop| dispone del botón **Importar pedidos**. Es importante
que los usuarios que van a importar pedidos tengan permisos a las tiendas del ERP
para generar los pedidos.

La importación de pedidos se realiza según intervalo de fechas:

Un ejemplo de fecha "04/10/2010 00:00:00" se importarán los pedidos del día 4
de octubre a partir de las 00 de la noche hasta el dia y hora que estamos
ejecutando la acción en el caso que la fecha final esté vacía.

Si especifica una fecha final, por ejemplo "04/10/2010 10:00:00", se importarán
los pedidos como antes, pero hasta las 10 de la mañana del mismo dia.

Si a Prestashop dispone de muchos pedidos de venta a partir de una fecha, una buena
opción es ir importando los pedidos en bloques y evitar la importación en masa.

El tiempo de importación de pedidos vendrá decidido según la cantidad de pedidos
a procesar.

.. note:: Si no gestiona los productos en el ERP, al recibir un pedido de venta
          se buscará un producto por el código. Si el producto existe, se usará
          este producto. Si el producto no existe, se creará un nuevo producto.
          Los datos del producto a crear son los valores del producto que disponga
          a Prestashop. En el caso de los impuestos, se buscará el impuesto que tenga
          añadido a Prestashop y buscará el equivalente al ERP según el país por defecto
          definido en la tienda.
          En el caso que el producto a Prestashop no tenga código, se creará un código
          al producto que consiste en: 'id-app,id-producto'.

Si un pedido de venta ya se ha importado, este pedido de venta no se volverá a crear.
Si por cualquier motivo desea volver a importar el pedido de venta, puede eliminar el
pedido de venta del ERP y volver a importar por el rango de fechas.
Como que el pedido no se encontrará por número de referencia y por tienda, se volverá
a crear.

La importación de pedidos de venta creará juntamente con el pedido de venta el tercero
y las direcciones. Si el tercero o la dirección ya existen estas no se volverán a crear.

Creación del tercero
--------------------

Antes de crear un tercero se buscará un existente con una de estas condiciones:

* Código país + Número NIF/CIF
* Número NIF/CIF
* Correo electrónico (pestaña eSale)
* Correo electrónico por defecto del tercero

La información del tercero nunca se modificará a partir de nuevos datos del Prestashop.

Reglas de impuestos
-------------------

En el caso que disponga de reglas de impuestos (para Melilla, Islas Canarias o un país
que no sea España), deberá crear un listado que relacione las reglas de impuestos según
subdivisiones o códigos postales que equivale por cada regla de impuesto especial. La configuración
de esta rejilla la podrá crear en el apartado de la configuración de la tienda.

Si el pedido de venta dispone en la dirección de facturación una región, se buscará
la subdivisión en la configuración de "Regla de impuestos" y los reglas
de impuesto equivalentes. En el caso que no se disponga de región, se buscará el
rango por código postal (inicio y final del código postal) si se dispone de una regla
de impuesto en este caso (los códigos postales deben ser numéricos).

En el caso que no disponga ni de región o código postal numérico, se usará la primera
regla de impuesto que se disponga por el país.

En el caso que la dirección de facturación de Prestashop del tercero encuentre uno de estos casos
esmentados, cuando se crea el tercero se le asignará una regla de impuestos en el tercero
y en el pedido de venta se le crearán los impuestos correspondientes a la regla de impuesto.

Creación de la dirección
------------------------

Antes de crear una dirección del tercero se buscará una existente con las condiciones:

* Tercero
* Calle
* Código postal

Las direcciones se crean con carácteres alfanuméricos (az09) (eliminando accentos y
carácteres que las API's de transporte se debe evitar).

Si la dirección creada desde Prestashop desea modificarla, recuerda también de modificar
la dirección en el cliente a Prestashop para que si el cliente la vuelve a usar no
se vuelva a crear una de nueva.

La información de la dirección nunca se modificará a partir de nuevos datos del Prestashop.
Si la dirección cambia de datos, se creará una nueva dirección con los nuevos datos.

Líneas
------

Cuando importe un pedido de venta se crearán las líneas del pedido. Es importante que
los productos de Prestashop esten creados también al ERP con el mismo código o referencia.
Si el producto no está creado al ERP (no se encuentra), se creará un nuevo producto.

El precio siempre es el que proviene de Prestashop y no se calculará un nuevo precio
cuando se genere el pedido de venta.

.. inheritref:: prestashop/prestashop:section:exportar_estado

Exportar estado
===============

En el menú |menu_sale_shop| dispone del botón de **Exportar estados** el cual
sincroniza los estados de Prestashop con los del ERP de los pedidos a partir de la
fecha especificada (fecha de modificación del pedido).

.. |menu_sale_shop| tryref:: sale_shop.menu_sale_shop/complete_name

.. inheritref:: prestashop/prestashop:section:configuracion_app

Configuración APP
=================

La configuración inicial es técnica y se efectuará en el momento de dar de alta
un servidor Prestashop en el ERP. Para configurar el servidor de Prestashop acceda a
|menu_prestashop_app|.

.. |menu_prestashop_app| tryref:: prestashop.menu_prestashop_app_form/complete_name

* Nombre

  * Nombre informativo del servidor de Prestashop
  
* General

  * Store View por defecto (disponible después de importar Prestashop Store)
  * Grupo de clientes por defecto (disponible después de importar grupo de
    clientes)
    
* Autenticación

  * URI del servidor Prestashop (con / al final).
  * AuthKey.
  
* Importar

  * Importar Prestashop Store: Importa toda la estructura de las tiendas de
    Prestashop y genera una tienda Prestashop en |menu_sale_shop|.
  * Importar grupo de clientes: Importa todos los grupos de clientes de Prestashop.
  * Importar impuestos: Importa toda la estructura de impuestos definida a Prestashop.

* Países

  * Países: Países que queremos importar regiones de Prestashop para los pedidos
    de venta.
  * Provincias: Asocia las provincias de Prestashop con las subdivisiones de Tryton.
  
* Tiendas

  * Información de nuestro Prestashop APP con la estructura de website/store/view

.. inheritref:: prestashop/prestashop:section:configuracion_tienda

Configuración de la tienda
==========================

A |menu_sale_shop| configure los valores de la tienda Prestashop. Fíjese que en
las tiendas Prestashop, el campo **APP tienda** marcará que es una tienda Prestashop.

En la configuración de la tienda esale, dispone de una pestaña más referente a
la configuración de la tienda Prestashop. De todos modos, revise la configuración
de todos los campos relacionados con la tienda.

* **Referencia Prestashop:** Usar el número de pedido de Prestashop
* **Precio global:** Para los multiestores, si se usa precio global o no (sólo
  para actualizaciones de precio)
* **Estados importación:** A partir del estado del pedido a Prestashop, podemos
  activar el pedido a Tryton si se confirma o se cancela.
* **Exportar estados:** Según el estado de Tryton, marcar el estado a Prestashop
  y/o notificar al cliente.
* **Métodos de pago:** Relaciona los pagos de Prestashop con los pagos de Tryton
* **Categoría:** Categoría por defecto. **Importante** que esta categoría tenga una
  cuenta a pagar y una cuenta a cobrar marcada.
